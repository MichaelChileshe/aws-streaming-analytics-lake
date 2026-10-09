# Teardown

Everything this project created is in Terraform's state, except one thing it changed: the account's Lake Formation settings. So the teardown is: stop the fleet, take the settings out of the state, destroy, put the settings back, check.

## 1. Stop the fleet and collect the results

```bash
# from the repo folder
python3 scripts/ssm_run.py sh "$SIM_ID" "systemctl stop fleet-sim; sleep 2; journalctl -u fleet-sim --no-pager -o cat | grep '^RESULT' | tail -n 1" | tee build/results/sim-totals.txt
python3 scripts/results.py | tee build/results/summary.txt
```

In this build: **414,660 sent in 6,910 s, 0 lost**, and Firehose's hourly totals matched ([`46`](screenshots/46-simulator-stopped-firehose-hourly.png)).

If the Quick Sight dashboard was used: remove its grant first (delete the `quicksight_principal_arn` line, apply: `1 destroyed`), then turn termination protection off and delete the subscription ([`lake-formation.md`](lake-formation.md)).

## 2. Destroy, without touching the account's settings

```bash
terraform -chdir=infra state rm aws_lakeformation_data_lake_settings.this
terraform -chdir=infra destroy -no-color 2>&1 | tee build/results/tf-destroy.txt
```

`state rm` makes Terraform forget the settings resource; nothing changes in AWS, and I stay data lake administrator while the destroy revokes the grants. Destroying it instead would, going by the provider's implementation, clear the administrators and default permissions and set the cross-account version to `"1"`.

The destroy deletes the database (and with it `fleet_history`, the table the CTAS made), empties and deletes the three buckets (`force_destroy`), deletes the enhanced fan-out consumer before the stream (and `enforce_consumer_deletion` means a consumer registered outside Terraform couldn't block it), and terminates the simulator. In this build: `Plan: 0 to add, 0 to change, 62 to destroy.` ([`results/raw/tf-destroy.txt`](results/raw/tf-destroy.txt)) and **`Destroy complete! Resources: 62 destroyed.`**, the stream taking 13 s ([`52`](screenshots/52-destroy-plan-workgroups.png), [`53`](screenshots/53-destroy-complete-62.png)).

## 3. Put the account's Lake Formation settings back

```bash
python3 scripts/lf_settings.py show       # still the project's: admin = me, no default permissions
python3 scripts/lf_settings.py restore    # the snapshot taken before the first apply
python3 scripts/lf_settings.py diff | tee build/results/lf-settings-after.txt
```

In this build: before the restore, admins `["user/Michael-admin"]` and empty defaults; after it, no admins and `IAM_ALLOWED_PRINCIPALS=ALL` for new databases and tables, `CROSS_ACCOUNT_VERSION` `"4"`; diff: **`identical to the snapshot taken before the build`** ([`54`](screenshots/54-lake-formation-settings-restored-identical.png)).

## 4. Clean check

Every line must print nothing, except the first (`0`) and the last (the empty state file). The filters use `mvela-` with the hyphen: `mvela` alone also matches other projects' `mvelaphanda-*` resources ([`debugging-journey.md`](debugging-journey.md)).

```bash
terraform -chdir=infra state list | wc -l
aws kinesis list-streams --query 'StreamNames[?starts_with(@, `mvela-`)]' --output text
aws firehose list-delivery-streams --query 'DeliveryStreamNames[?starts_with(@, `mvela-`)]' --output text
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `mvela-`)].FunctionName' --output text
aws glue get-databases --query 'DatabaseList[?starts_with(Name, `mvela_`)].Name' --output text
aws lakeformation list-resources --query 'ResourceInfoList[?contains(ResourceArn, `mvela-`)].ResourceArn' --output text
aws athena list-work-groups --query 'WorkGroups[?starts_with(Name, `mvela-`)].Name' --output text
aws s3api list-buckets --query 'Buckets[?starts_with(Name, `mvela-`)].Name' --output text
aws iam list-roles --query 'Roles[?starts_with(RoleName, `mvela-`)].RoleName' --output text
aws iam list-instance-profiles --query 'InstanceProfiles[?starts_with(InstanceProfileName, `mvela-`)].InstanceProfileName' --output text
aws ec2 describe-instances --filters Name=tag:Name,Values=mvela-fleet-sim Name=instance-state-name,Values=pending,running,stopping,stopped --query 'Reservations[].Instances[].InstanceId' --output text
aws ec2 describe-vpcs --filters Name=tag:Name,Values=mvela-lake-vpc --query 'Vpcs[].VpcId' --output text
aws logs describe-log-groups --query 'logGroups[?contains(logGroupName, `mvela-`)].logGroupName' --output text
aws cloudwatch describe-alarms --alarm-name-prefix mvela- --query 'MetricAlarms[].AlarmName' --output text
aws s3 ls "s3://$STATE_BUCKET/aws-streaming-analytics-lake/"
```

Result in this build: state list `0`, nothing of this project left, and a 610-byte `terraform.tfstate` (an empty state) in the state bucket. My run used `mvela` without the hyphen and listed four `mvelaphanda-*` resources from `aws-resource-hygiene-automation` and `aws-cost-billing-dashboard`, which stay ([`55`](screenshots/55-clean-check.png)).

**What stays on purpose:** the shared state bucket (`bootstrap/`, with `prevent_destroy`), the Glue `default` database (empty, free; created before the build), Quick Sight's IAM service roles (free), and the `Mvelaphanda/Fleet` custom metrics, which can't be deleted and expire on their own.
