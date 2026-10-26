# Exasol Personal Deployment Guide

This guide details the exact lifecycle procedures for deploying, managing, and destroying Exasol Personal instances for **Regret Radar** across local and AWS environments.

---

## 1. Prerequisites and Launcher CLI Installation

The `exasol` launcher CLI manages the lifecycle of Exasol Personal deployments.

### Windows (PowerShell)
```powershell
# Install Exasol Personal Starter Kit (installs exasol CLI and container tooling)
irm https://www.exasol.com/install/starter-kit.ps1 | iex
```

### macOS / Linux
```bash
curl -fsSL https://raw.githubusercontent.com/exasol/exasol-personal/main/install.sh | sh
```

### Verify Launcher
```bash
exasol version
```

---

## 2. Local Deployment

Local deployment runs Exasol Personal on your workstation using container virtualization (Docker Desktop / Podman on Windows, lightweight VM on macOS).

### Start / Install Local Database
To install the default local deployment:
```powershell
exasol install local
```

To install with a named deployment:
```powershell
exasol install local -d regret-radar-local
```

### Enable Python UDF Support
If Python script language container (SLC) is not pre-installed in your local preset:
```powershell
exasol slc install python
```

### Verify Local Deployment
```powershell
# List all active deployments
exasol deployments list

# Display detailed connection information
exasol info

# Test SQL connectivity with the built-in client
exasol connect -c "SELECT 1;"
```

---

## 3. AWS Cloud Deployment

> [!WARNING]
> **Cloud Cost Warning**: Provisioning to AWS deploys real EC2 compute instances, EBS volumes, and networking resources in your AWS account. These incur continuous hourly cloud charges. A deployment takes 10–20 minutes and must never be interrupted prematurely; an interrupted deployment can leave orphaned billable resources running in your cloud account.

### Step 1: Prepare AWS Account & Credentials
Ensure the AWS CLI is configured with credentials that have permission to create VPCs, security groups, and EC2 instances:
```powershell
aws configure
aws sts get-caller-identity
```

### Step 2: Deploy to AWS
Execute the install command (the AWS region is resolved from your active AWS profile):
```powershell
# Default deployment
exasol install aws

# Or named deployment with custom cluster options
exasol install aws -d regret-radar-aws
```

Wait until the deployment status transitions to `database_ready` / `running`.

---

## 4. Stopping and Resuming Deployments

When you are not running queries, you can pause the database to save compute resources without losing data.

### Stop Deployment
```powershell
# Stop default deployment
exasol stop

# Stop a named deployment
exasol stop -d regret-radar-aws
```
> [!NOTE]
> On AWS, stopping an instance pauses EC2 compute billing, but associated EBS storage and Elastic IPs continue to accrue nominal charges. In addition, public IP addresses may change upon restart.

### Start Deployment
```powershell
# Resume default deployment
exasol start

# Resume a named deployment
exasol start -d regret-radar-aws
```

---

## 5. Destroying Deployments

> [!CAUTION]
> **Permanent Deletion**: `exasol destroy` permanently deletes the database, schemas, tables, and all provisioned cloud infrastructure.
> **Critical Rule**: Never manually delete the deployment directory (`~/.exasol/personal/deployments/<name>`) without running `exasol destroy` first! Deleting the local files leaves cloud resources running orphaned in your account, accumulating cloud bills.

### Destroy Procedure
```powershell
# Destroy default deployment
exasol destroy

# Destroy a named deployment
exasol destroy -d regret-radar-aws
```
Review the confirmation prompt and type `yes` to confirm termination of all cloud/local resources.

---

## 6. Configuring Regret Radar Connection

Once your Exasol deployment is running:

1. Copy credentials into `.env`:
   ```env
   EXASOL_HOST=127.0.0.1
   PORT=8563
   USER=sys
   PASSWORD=<your_database_password>
   ```
   *(For local deployments, the initial password is automatically generated in `~/.exasol/personal/deployments/default/secrets.json`)*

2. Verify connectivity and initialize the `REGRET_RADAR` schema:
   ```powershell
   python check_db.py
   ```
