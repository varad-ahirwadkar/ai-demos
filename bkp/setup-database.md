# Setup PostgreSQL Database

Since the socket is in a custom location, you must connect via TCP (using `-h 127.0.0.1`) instead of Unix socket.

## Create the llamastack database

```bash
oc exec -it deployment/pgvector-postgresql-deployment -- \
  psql -h 127.0.0.1 -U llamastack -d postgres -c "CREATE DATABASE llamastack;"
```

## Create pgvector extension

```bash
oc exec -it deployment/pgvector-postgresql-deployment -- \
  psql -h 127.0.0.1 -U llamastack -d llamastack -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Verify installation

```bash
oc exec -it deployment/pgvector-postgresql-deployment -- \
  psql -h 127.0.0.1 -U llamastack -d llamastack -c "\dx"
```

## Test vector operations

```bash
oc exec -it deployment/pgvector-postgresql-deployment -- \
  psql -h 127.0.0.1 -U llamastack -d llamastack <<'EOF'
-- Create test table
CREATE TABLE test_vectors (
  id serial PRIMARY KEY,
  embedding vector(3)
);

-- Insert test data
INSERT INTO test_vectors (embedding) VALUES 
  ('[1,2,3]'),
  ('[4,5,6]'),
  ('[7,8,9]');

-- Query by similarity
SELECT id, embedding 
FROM test_vectors 
ORDER BY embedding <-> '[3,1,2]' 
LIMIT 2;

-- Cleanup
DROP TABLE test_vectors;
EOF
```

## Connect interactively

```bash
# Always use -h 127.0.0.1 to connect via TCP
oc exec -it deployment/pgvector-postgresql-deployment -- \
  psql -h 127.0.0.1 -U llamastack -d llamastack
```

## Important Notes

- **Always use `-h 127.0.0.1`** when connecting with psql
- The Unix socket is in `/var/lib/postgresql/data/run/` (not the default `/var/run/postgresql/`)
- TCP connections work fine since PostgreSQL is listening on 0.0.0.0:5432