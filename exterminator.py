import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta
import tableprint as tp
import numpy as np

load_dotenv()

ec2_client = boto3.client('ec2')

response = ec2_client.describe_regions()
regions = list(map(lambda x: x['RegionName'], response['Regions']))

regions_clients = {region: boto3.resource('ec2', region_name=region) for region in regions}
regions_cloudwatches = {region: boto3.client('cloudwatch', region_name=region) for region in regions}


def find_all_instances():
    instances_dict = {}
    for reg in regions:
        print(f"\rAnalysing region '{reg}'...", end='')

        ec2 = regions_clients[reg]
        instances = list(ec2.instances.all())

        if len(instances) > 0:
            instances_dict[reg] = {}
        else:
            continue
        for instance in instances:
            instances_dict[reg][instance.id] = {"instance": instance, "metrics": {}}
            watch = regions_cloudwatches[reg]
            metrics = watch.list_metrics(Namespace='AWS/EC2', Dimensions=[{"Name": "InstanceId",
                                                                           "Value": instance.id}])
            metrics = metrics['Metrics']
            for met in metrics:
                response = watch.get_metric_statistics(Namespace=met['Namespace'], MetricName=met['MetricName'], Dimensions=met['Dimensions'], Statistics=[
                    'SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum',
                ], Period=300, EndTime=datetime.utcnow(), StartTime=datetime.utcnow() - timedelta(seconds=600))
                if not response or not response['Datapoints']:
                    continue
                data = response['Datapoints'][0]
                instances_dict[reg][instance.id]['metrics'] = {"name": met, "min": data['Minimum'], "max": data['Maximum'], "avg": data['Average'],
                                                               "unit": data['Unit']}
    print("\r...Got all instances")
    return instances_dict


def instances_pretty_print(instances):
    def get_instance_array(instance_entry):
        instance = instance_entry['instance']
        name = next((item['Value'] for item in instance.tags if item["Key"] == "Name"), "-----")
        return np.array(
            [instance.launch_time.strftime("%m/%d/%Y, %H:%M:%S"), instance.id, name, instance.instance_type, instance.image_id, instance.state['Name'],
             instance.public_dns_name])

    for region in instances.keys():
        print(f"{region}:")
        headers = np.array(["Creation Date", "ID", "Name", "Type", "AMI", "State", "Public DNS"])
        data = np.array(list(map(get_instance_array, instances[region].values())))
        np_len = np.vectorize(len)
        width = np_len(np.append(headers.reshape(1, -1), data, axis=0)).max(axis=0)
        tp.table(data, headers, width=width)


all_instances = find_all_instances()

if len(all_instances) == 0:
    print("You don't have any instances running...bye...")
    exit(0)

running = True

instances_pretty_print(all_instances)
# List all instances
while running:
    key = input("""What would you like to do?
Type 'q' to quit
Type 'd' to select an instance to delete
Type 'v' to view metrics for an instance
Type 'r' to refresh the instances data
""")

    if key == 'q':
        running = False
    elif key == 'd':
        # TODO find suitable instances to delete
        pass
    elif key == 'v':
        pass
    elif key == 'r':
        all_instances = find_all_instances()
        instances_pretty_print(all_instances)
    else:
        print("Unsupported operation")

print("Bye")
