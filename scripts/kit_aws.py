"""Shared helpers for the kit's scripts: call the AWS CLI the same way everywhere, fail loudly,
keep results in build/results/, and act as the analyst role when a script needs to."""
import json
import os
import subprocess
import sys

# The repo folder (where env.sh lives). env.sh exports WORKDIR; fall back to the parent of scripts/.
ROOT = os.environ.get("WORKDIR") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "build", "results")


def aws(*args):
    """Run `aws <args> --output json` and return parsed JSON (or {} for empty output)."""
    ok, data, err = aws_try(*args)
    if not ok:
        sys.exit(f"\nFAILED: aws {' '.join(args[:2])}\n{err}\n")
    return data


def aws_try(*args):
    """Like aws(), but returns (ok, data, stderr) instead of exiting: for calls that SHOULD fail."""
    res = subprocess.run(["aws", *args, "--output", "json"], capture_output=True, text=True)
    if res.returncode != 0:
        return False, {}, res.stderr.strip()
    return True, (json.loads(res.stdout) if res.stdout.strip() else {}), ""


def env(name):
    """Read a saved value from the environment, with a clear message if it is missing."""
    val = os.environ.get(name, "")
    if not val:
        sys.exit(f"\nMISSING: ${name} is not set. Run:  source ./env.sh  (from the repo folder)\n")
    return val


def save(name, value):
    """Same as the save() shell function: export for this run + append to env.sh."""
    os.environ[name] = value
    with open(os.path.join(ROOT, "env.sh"), "a") as f:
        f.write(f'export {name}="{value}"\n')
    print(f"saved {name}={value}")


def write_result(name, obj):
    """build/results/<name>.json, pretty-printed (these files go into the repo)."""
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, f"{name}.json")
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=str)
    return path


def become(role_arn, session="mvela-analyst-check"):
    """Switch THIS process (and the aws CLI calls it makes) to the role's temporary credentials.
    The keys are never printed. Returns the assumed-role ARN."""
    creds = aws("sts", "assume-role", "--role-arn", role_arn, "--role-session-name", session,
                "--duration-seconds", "3600")["Credentials"]
    for k in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE"):
        os.environ.pop(k, None)
    os.environ["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
    os.environ["AWS_SESSION_TOKEN"] = creds["SessionToken"]
    return aws("sts", "get-caller-identity")["Arn"]
