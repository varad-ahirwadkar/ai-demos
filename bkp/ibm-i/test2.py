import subprocess

def query_ibm_i(sql):
    # We wrap the command in 'qsh -c' to ensure the Db2 environment is loaded
    # and use -q to keep SSH quiet.
    cmd = f"ssh -q aaruni@9.114.98.63 \"/usr/bin/qsh -c 'db2 \\\"{sql}\\\"'\""
    
    try:
        # We use stderr=subprocess.STDOUT to see the actual error if it fails again
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode()
        return result
    except subprocess.CalledProcessError as e:
        return f"Shell Error: {e.output.decode()}"
    except Exception as e:
        return f"Other Error: {e}"

print(query_ibm_i("SELECT * FROM TECHMART.ORDERS"))