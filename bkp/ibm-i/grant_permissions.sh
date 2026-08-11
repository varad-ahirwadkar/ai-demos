#!/bin/bash
# Script to grant IBM i DB2 permissions for user AARUNI

echo "Granting IBM i DB2 permissions for user AARUNI..."
echo "=================================================="

# 1. Grant QZDASOINIT program access (DONE - you already ran this)
echo "1. Granting QZDASOINIT program access..."
system "GRTOBJAUT OBJ(QSYS/QZDASOINIT) OBJTYPE(*PGM) USER(AARUNI) AUT(*USE)"

# 2. Grant QSYS library access
echo "2. Granting QSYS library access..."
system "GRTOBJAUT OBJ(QSYS) OBJTYPE(*LIB) USER(AARUNI) AUT(*USE)"

# 3. Grant TECHMART library access
echo "3. Granting TECHMART library access..."
system "GRTOBJAUT OBJ(TECHMART) OBJTYPE(*LIB) USER(AARUNI) AUT(*ALL)"

# 4. Grant ORDERS table access
echo "4. Granting ORDERS table access..."
system "GRTOBJAUT OBJ(TECHMART/ORDERS) OBJTYPE(*FILE) USER(AARUNI) AUT(*ALL)"

echo "=================================================="
echo "✓ All permissions granted!"
echo ""
echo "Now test the connection with:"
echo "  python test2.py"

# Made with Bob
