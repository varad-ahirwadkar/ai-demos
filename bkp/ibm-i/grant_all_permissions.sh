#!/bin/bash
# Comprehensive permission grant script for IBM i DB2 access

echo "============================================================"
echo "Granting Comprehensive IBM i DB2 Permissions for AARUNI"
echo "============================================================"

echo ""
echo "Step 1: Grant QZDASOINIT program authority..."
system "GRTOBJAUT OBJ(QSYS/QZDASOINIT) OBJTYPE(*PGM) USER(AARUNI) AUT(*USE)"

echo ""
echo "Step 2: Grant QSYS library authority..."
system "GRTOBJAUT OBJ(QSYS) OBJTYPE(*LIB) USER(AARUNI) AUT(*USE)"

echo ""
echo "Step 3: Grant QSYS2 library authority..."
system "GRTOBJAUT OBJ(QSYS2) OBJTYPE(*LIB) USER(AARUNI) AUT(*USE)"

echo ""
echo "Step 4: Grant TECHMART library authority..."
system "GRTOBJAUT OBJ(TECHMART) OBJTYPE(*LIB) USER(AARUNI) AUT(*ALL)"

echo ""
echo "Step 5: Grant ORDERS table authority..."
system "GRTOBJAUT OBJ(TECHMART/ORDERS) OBJTYPE(*FILE) USER(AARUNI) AUT(*ALL)"

echo ""
echo "Step 6: Check user profile special authorities..."
system "DSPUSRPRF USRPRF(AARUNI)" | grep -i "special"

echo ""
echo "============================================================"
echo "Additional Commands to Try (if above doesn't work):"
echo "============================================================"
echo ""
echo "Option 1: Add user to QSECOFR group"
echo "  system \"CHGUSRPRF USRPRF(AARUNI) GRPPRF(QSECOFR)\""
echo ""
echo "Option 2: Grant special authorities"
echo "  system \"CHGUSRPRF USRPRF(AARUNI) SPCAUT(*JOBCTL)\""
echo ""
echo "Option 3: Change user class"
echo "  system \"CHGUSRPRF USRPRF(AARUNI) USRCLS(*SECOFR)\""
echo ""
echo "Option 4: Grant authority to all QSYS objects"
echo "  system \"GRTOBJAUT OBJ(QSYS/*ALL) OBJTYPE(*ALL) USER(AARUNI) AUT(*USE)\""
echo ""
echo "============================================================"

# Made with Bob
