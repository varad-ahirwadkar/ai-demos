#!/bin/bash
# Check IBM i DB2 server status and configuration

echo "============================================================"
echo "IBM i DB2 Server Status Check"
echo "============================================================"

echo ""
echo "1. Checking QZDASOINIT jobs in QUSRWRK subsystem..."
system "WRKACTJOB SBS(QUSRWRK)" | grep -i QZDASO || echo "No QZDASOINIT jobs found"

echo ""
echo "2. Checking if QUSRWRK subsystem is active..."
system "WRKACTJOB SBS(QUSRWRK)" | head -20

echo ""
echo "3. Checking service table entries..."
system "WRKSRVTBLE" | grep -E "as-database|drda|ddm"

echo ""
echo "4. Checking database server configuration..."
system "WRKDBSVR"

echo ""
echo "5. Checking prestart job entries..."
system "WRKPJE SBSD(QUSRWRK)" | grep -i QZDASO

echo ""
echo "============================================================"
echo "Recommendations:"
echo "============================================================"
echo "If no QZDASOINIT jobs found, run:"
echo "  system \"CHGPJE SBSD(QUSRWRK) PGM(QZDASOINIT) INLJOBS(10)\""
echo "  system \"ENDSBS SBS(QUSRWRK) OPTION(*IMMED)\""
echo "  system \"STRSBS SBSD(QUSRWRK)\""
echo ""
echo "Or start database server:"
echo "  system \"STRHOSTSVR SERVER(*DATABASE)\""
echo "============================================================"

# Made with Bob
