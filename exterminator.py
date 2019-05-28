import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta
import tableprint as tp
import numpy as np
from PyInquirer import prompt

load_dotenv()

ec2_client = boto3.client('ec2')

response = ec2_client.describe_regions()
regions = list(map(lambda x: x['RegionName'], response['Regions']))

regions_clients = {region: boto3.resource('ec2', region_name=region) for region in regions}
regions_cloudwatches = {region: boto3.client('cloudwatch', region_name=region) for region in regions}

np_len = np.vectorize(len)


def find_all_instances():
    instances_dict = {}
    all_metrics = []
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
                if not next((x for x in all_metrics if x['name'] == met['MetricName']), None):
                    all_metrics.append({'name': met['MetricName'], 'value': met})
    print("\r...Got all instances")
    return instances_dict, all_metrics


def get_instance_link(region, instance_id):
    return f"https://console.aws.amazon.com/ec2/v2/home?region={region}#Instances:instanceId={instance_id};sort=instanceId"


def instances_pretty_print(instances):
    def get_instance_array(instance_entry):
        instance = instance_entry['instance']
        if instance.tags:
            name = next((item['Value'] for item in instance.tags if item["Key"] == "Name"), "-----")
        else:
            name = "-----"
        return np.array(
            [instance.launch_time.strftime("%m/%d/%Y, %H:%M:%S"), instance.id, name, instance.instance_type, instance.image_id, instance.state['Name'],
             instance.public_dns_name])

    for region in instances.keys():
        print(f"{region}:")
        headers = np.array(["Creation Date", "ID", "Name", "Type", "AMI", "State", "Public DNS"])
        data = np.array(list(map(get_instance_array, instances[region].values())))
        width = np_len(np.append(headers.reshape(1, -1), data, axis=0)).max(axis=0)
        tp.table(data, headers, width=width)


def print_metrics(period, met, instances):
    print(met['MetricName'])
    for region in instances.keys():
        print(f"{region}:")
        headers = np.array(["ID", "Min", "Max", "Average", "Unit"])
        watch = regions_cloudwatches[region]
        metrics = []
        for instance_id in instances[region].keys():
            dimensions = [{'Name': 'InstanceId', 'Value': instance_id}]
            response = watch.get_metric_statistics(Namespace=met['Namespace'], MetricName=met['MetricName'], Dimensions=dimensions, Statistics=[
                'SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum',
            ], Period=period, EndTime=datetime.utcnow(), StartTime=datetime.utcnow() - timedelta(seconds=period))
            if not response or not response['Datapoints']:
                continue
            data = response['Datapoints'][0]
            metrics.append([instance_id, data['Minimum'], data['Maximum'], data['Average'], data['Unit']])
        metrics = np.array(metrics)
        width = np_len(np.append(headers.reshape(1, -1), metrics, axis=0)).max(axis=0)
        tp.table(metrics, headers, width=width)


all_instances, all_metrics = find_all_instances()

if len(all_instances) == 0:
    print("You don't have any instances running...bye...")
    exit(0)

running = True

menu_question = [{
    'type': 'list',
    'name': 'menu',
    'message': 'What do you want to do next?',
    'choices': [
        {'name': "Refresh instance list", 'value': 'r'},
        {'name': "Choose an instance to delete", 'value': 'd'},
        {'name': "View metrics", 'value': 'v'},
        {'name': "Quit", 'value': 'q'},
    ]
}]
instances_pretty_print(all_instances)
# List all instances
while running:
    menu_answer = prompt(menu_question)
    key = menu_answer['menu']

    if key == 'q':
        running = False
    elif key == 'd':
        # TODO find suitable instances to delete
        pass
    elif key == 'v':

        metrics_questions = [{
            'type': 'list',
            'name': 'metric',
            'message': 'What metric do you want to see?',
            'choices': all_metrics
        }, {
            'type': 'list',
            'name': 'duration',
            'message': 'For how long?',
            'choices': [
                {'name': '10 minutes', 'value': 600},
                {'name': '1 hour', 'value': 3600},
                {'name': '24 hours', 'value': 86400}
            ]
        }]
        answers = prompt(metrics_questions)
        print_metrics(answers['duration'], answers['metric'], all_instances)
        pass
    elif key == 'r':
        all_instances, all_metrics = find_all_instances()
        instances_pretty_print(all_instances)
    else:
        print("Unsupported operation")

print("Bye")
