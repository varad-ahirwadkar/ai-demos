#!/bin/bash
# manage-demo.sh — Deploy or delete TechMart OGX demo resources
#
# Run from the openshift-ai-demos/ directory:
#
#   bash ogx-demos/techmart-customer-service-demo/scripts/manage-demo.sh deploy
#   bash ogx-demos/techmart-customer-service-demo/scripts/manage-demo.sh delete
#   bash ogx-demos/techmart-customer-service-demo/scripts/manage-demo.sh deploy --all
#   bash ogx-demos/techmart-customer-service-demo/scripts/manage-demo.sh delete --all

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { printf "${BLUE}ℹ️  %s${NC}\n" "$*"; }
success() { printf "${GREEN}✅ %s${NC}\n" "$*"; }
warn()    { printf "${YELLOW}⚠️  %s${NC}\n" "$*"; }
error()   { printf "${RED}❌ %s${NC}\n" "$*"; }
header()  { printf "\n${BOLD}${BLUE}=== %s ===${NC}\n" "$*"; }

# ---------------------------------------------------------------------------
# Preflight: must be run from openshift-ai-demos/
# ---------------------------------------------------------------------------
preflight() {
    if ! command -v oc &>/dev/null; then
        error "'oc' not found. Install the OpenShift CLI and try again."
        exit 1
    fi
    if ! oc whoami &>/dev/null; then
        error "Not logged in to OpenShift. Run 'oc login' first."
        exit 1
    fi
    if [[ ! -f "ogx-demos/techmart-customer-service-demo/deployments/techmart-ui.yaml" ]]; then
        error "Script must be run from the openshift-ai-demos/ directory."
        error "Example: bash ogx-demos/techmart-customer-service-demo/scripts/manage-demo.sh ${ACTION}"
        exit 1
    fi
    info "Cluster : $(oc whoami --show-server 2>/dev/null)"
    info "Project : $(oc project -q)"
    echo ""
}

# ---------------------------------------------------------------------------
# Resource catalogue — parallel indexed arrays (works on bash 3+)
# Index i in every array describes the same resource.
# ---------------------------------------------------------------------------
DEMO_DIR="ogx-demos/techmart-customer-service-demo"
DEPLOY_DIR="${DEMO_DIR}/deployments"
SHARED_DIR="ogx-demos/shared"

# pgvector is intentionally excluded — OGX uses inline::faiss + shared postgres.
# See deployments/pgvector.yaml for the manifest if needed.
RES_KEYS=(
    app_postgres
    db_init
    mcp_server
    ui
    ogx_postgres
    ogx_server
)

RES_LABELS=(
    "App PostgreSQL (order data)"
    "DB Init Job (schema + sample data)"
    "TechMart MCP Server"
    "TechMart UI"
    "OGX Postgres (shared)"
    "OGX Server"
)

RES_YAMLS=(
    "${DEPLOY_DIR}/postgresql-mcp.yaml"
    "${DEPLOY_DIR}/db-init-job.yaml"
    "${DEPLOY_DIR}/techmart-mcp-server.yaml"
    "${DEPLOY_DIR}/techmart-ui.yaml"
    "${SHARED_DIR}/postgres.yaml"
    "${DEPLOY_DIR}/ogx-server.yaml"
)

# readiness wait commands — empty string means skip
RES_WAITS=(
    "oc wait --for=condition=ready pod -l app=techmart-postgresql --timeout=180s"
    "oc wait --for=condition=complete job/techmart-db-init --timeout=180s"
    "oc wait --for=condition=available deployment/techmart-mcp-server --timeout=180s"
    "oc wait --for=condition=available deployment/techmart-ui --timeout=180s"
    "oc wait --for=condition=ready pod -l app=postgres --timeout=180s"
    "oc wait --for=condition=ready pod -l app=ogx --timeout=300s"
)

# pre-deploy cleanup — empty string means none
RES_PRE_DEPLOY=(
    ""
    "oc delete job techmart-db-init --ignore-not-found=true"
    ""
    ""
    ""
    ""
)

# ---------------------------------------------------------------------------
# Look up the array index for a given key
# ---------------------------------------------------------------------------
index_of() {
    local key="$1"
    for i in "${!RES_KEYS[@]}"; do
        [[ "${RES_KEYS[$i]}" == "$key" ]] && echo "$i" && return
    done
    echo "-1"
}

# ---------------------------------------------------------------------------
# Interactive multi-select menu
# Accepts: comma/space-separated numbers, ranges (N-M), or 'a' for all.
# Populates global SELECTED_INDICES array.
# ---------------------------------------------------------------------------
select_resources() {
    local action="$1"

    header "Select resources to ${action}"
    printf "  ${CYAN}a${NC}  All of the above\n"
    for i in "${!RES_KEYS[@]}"; do
        printf "  ${CYAN}%d${NC}  %s\n" "$((i+1))" "${RES_LABELS[$i]}"
    done
    echo ""
    printf "Enter numbers (e.g. 1,3,5), a range (e.g. 2-4), or 'a' for all: "
    read -r raw

    SELECTED_INDICES=()

    if [[ "$raw" == "a" || "$raw" == "A" ]]; then
        for i in "${!RES_KEYS[@]}"; do SELECTED_INDICES+=("$i"); done
        return
    fi

    IFS=', ' read -ra tokens <<< "$raw"
    for token in "${tokens[@]}"; do
        if [[ "$token" =~ ^([0-9]+)-([0-9]+)$ ]]; then
            local lo="${BASH_REMATCH[1]}" hi="${BASH_REMATCH[2]}"
            for (( n=lo; n<=hi; n++ )); do
                local idx=$((n-1))
                [[ $idx -ge 0 && $idx -lt ${#RES_KEYS[@]} ]] && SELECTED_INDICES+=("$idx")
            done
        elif [[ "$token" =~ ^[0-9]+$ ]]; then
            local idx=$((token-1))
            [[ $idx -ge 0 && $idx -lt ${#RES_KEYS[@]} ]] && SELECTED_INDICES+=("$idx")
        fi
    done

    if [[ ${#SELECTED_INDICES[@]} -eq 0 ]]; then
        error "No valid selection. Exiting."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Deploy one resource by array index
# ---------------------------------------------------------------------------
deploy_resource() {
    local i="$1"
    local label="${RES_LABELS[$i]}"
    local yaml="${RES_YAMLS[$i]}"
    local wait="${RES_WAITS[$i]}"
    local pre="${RES_PRE_DEPLOY[$i]}"

    header "Deploying: ${label}"

    if [[ ! -f "$yaml" ]]; then
        error "Manifest not found: ${yaml}"
        error "Make sure you are running from the openshift-ai-demos/ directory."
        return 1
    fi

    if [[ -n "$pre" ]]; then
        info "Pre-deploy cleanup: ${pre}"
        eval "$pre" || true
        sleep 2
    fi

    oc apply -f "$yaml"
    success "Applied: ${yaml}"

    if [[ -n "$wait" ]]; then
        info "Waiting for readiness..."
        if eval "$wait"; then
            success "${label} is ready"
        else
            warn "${label} did not become ready within the timeout — check: oc get pods"
        fi
    fi

    # Show DB init logs after the job completes
    if [[ "${RES_KEYS[$i]}" == "db_init" ]]; then
        info "Init job logs:"
        oc logs job/techmart-db-init 2>/dev/null | sed 's/^/   /' || true
    fi

    # Print UI route after the UI deploys
    if [[ "${RES_KEYS[$i]}" == "ui" ]]; then
        local route
        route=$(oc get route techmart-ui -o jsonpath='{.spec.host}' 2>/dev/null || true)
        [[ -n "$route" ]] && success "UI available at: https://${route}" || true
    fi
}

# ---------------------------------------------------------------------------
# Delete one resource by array index
# ---------------------------------------------------------------------------
delete_resource() {
    local i="$1"
    local label="${RES_LABELS[$i]}"
    local yaml="${RES_YAMLS[$i]}"

    header "Deleting: ${label}"

    if [[ ! -f "$yaml" ]]; then
        error "Manifest not found: ${yaml}"
        error "Make sure you are running from the openshift-ai-demos/ directory."
        return 1
    fi

    oc delete -f "$yaml" --ignore-not-found=true
    success "Deleted resources from: ${yaml}"

    # DB init ConfigMaps are not part of the Job spec — delete them separately
    if [[ "${RES_KEYS[$i]}" == "db_init" ]]; then
        oc delete configmap techmart-db-scripts techmart-db-data --ignore-not-found=true
        success "Deleted DB init ConfigMaps"
    fi
}

# ---------------------------------------------------------------------------
# Confirm before deleting
# ---------------------------------------------------------------------------
confirm_delete() {
    echo ""
    warn "The following resources will be DELETED:"
    for i in "$@"; do
        printf "  • %s\n" "${RES_LABELS[$i]}"
    done
    echo ""
    printf "Type 'yes' to confirm: "
    read -r confirm
    [[ "$confirm" != "yes" ]] && { info "Aborted."; exit 0; }
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print_summary() {
    local action="$1"; shift
    header "Summary"
    for i in "$@"; do
        printf "  ${GREEN}✓${NC} %s: %s\n" "${action}" "${RES_LABELS[$i]}"
    done
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
ACTION="${1:-}"
FLAG="${2:-}"

if [[ -z "$ACTION" || ( "$ACTION" != "deploy" && "$ACTION" != "delete" ) ]]; then
    printf "${BOLD}Usage (run from openshift-ai-demos/):${NC}\n"
    echo "  bash ${DEMO_DIR}/scripts/manage-demo.sh deploy           # interactive"
    echo "  bash ${DEMO_DIR}/scripts/manage-demo.sh delete           # interactive"
    echo "  bash ${DEMO_DIR}/scripts/manage-demo.sh deploy --all     # deploy everything"
    echo "  bash ${DEMO_DIR}/scripts/manage-demo.sh delete --all     # delete everything"
    exit 1
fi

preflight

if [[ "$FLAG" == "--all" ]]; then
    SELECTED_INDICES=()
    for i in "${!RES_KEYS[@]}"; do SELECTED_INDICES+=("$i"); done
else
    select_resources "$ACTION"
fi

echo ""
info "Selected:"
for i in "${SELECTED_INDICES[@]}"; do
    printf "  • %s\n" "${RES_LABELS[$i]}"
done
echo ""

if [[ "$ACTION" == "deploy" ]]; then
    for i in "${SELECTED_INDICES[@]}"; do
        deploy_resource "$i"
    done
    print_summary "Deployed" "${SELECTED_INDICES[@]}"

elif [[ "$ACTION" == "delete" ]]; then
    confirm_delete "${SELECTED_INDICES[@]}"
    # Reverse the indices so dependents are removed before dependencies
    reversed=()
    for i in "${SELECTED_INDICES[@]}"; do reversed=("$i" "${reversed[@]}"); done
    for i in "${reversed[@]}"; do
        delete_resource "$i"
    done
    print_summary "Deleted" "${SELECTED_INDICES[@]}"
fi
