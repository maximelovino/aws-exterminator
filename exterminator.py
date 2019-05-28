import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta
import tableprint as tp
import numpy as np
from PyInquirer import prompt, Separator

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
            instances_dict[reg][instance.id] = {"instance": instance, "metrics": {}}  # TODO this does not need to be a dict
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


def metric_for_instance(period, met, instance_id, watch_client):
    dimensions = [{'Name': 'InstanceId', 'Value': instance_id}]
    response = watch_client.get_metric_statistics(Namespace=met['Namespace'], MetricName=met['MetricName'], Dimensions=dimensions, Statistics=[
        'SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum',
    ], Period=period, EndTime=datetime.utcnow(), StartTime=datetime.utcnow() - timedelta(seconds=period))
    if not response or not response['Datapoints']:
        raise Exception
    data = response['Datapoints'][0]
    return data


def print_metrics(period, met, instances):
    print(met['MetricName'])
    for region in instances.keys():

        headers = np.array(["ID", "Min", "Max", "Average", "Unit"])
        watch = regions_cloudwatches[region]
        metrics = []
        for instance_id in instances[region].keys():
            if not instances[region][instance_id]['instance'].state['Name'] == 'running':
                continue
            try:
                data = metric_for_instance(period, met, instance_id, watch)
                metrics.append([instance_id, data['Minimum'], data['Maximum'], data['Average'], data['Unit']])
            except:
                print(f"Couldn't get metrics for {instance_id}")
        if len(metrics) > 0:
            print(f"{region}:")
            metrics = np.array(metrics)
            width = np_len(np.append(headers.reshape(1, -1), metrics, axis=0)).max(axis=0)
            tp.table(metrics, headers, width=width)


def delete_instance(instance_id, region):
    client = boto3.client('ec2', region_name=region)
    client.terminate_instances(InstanceIds=[instance_id], DryRun=False)


def get_all_images():
    images_dict = {}
    for reg in regions:
        print(f"\rAnalysing region '{reg}'...", end='')

        ec2 = regions_clients[reg]
        images = list(ec2.images.filter(Owners=['self']))

        if len(images) > 0:
            images_dict[reg] = {}
        else:
            continue
        for image in images:
            images_dict[reg][image.id] = {"image": image}  # TODO this does not need to be a dict
    print("\r...Got all images")
    return images_dict


def images_pretty_print(images):
    def get_image_array(image_entry):
        image = image_entry['image']
        # For creation date, we should parse as datetime and then strftime("%m/%d/%Y, %H:%M:%S")
        return np.array(
            [image.creation_date, image.id, image.name, image.image_type])

    for region in images.keys():
        print(f"{region}:")
        headers = np.array(["Creation Date", "ID", "Name", "Type"])
        data = np.array(list(map(get_image_array, images[region].values())))
        width = np_len(np.append(headers.reshape(1, -1), data, axis=0)).max(axis=0)
        tp.table(data, headers, width=width)


def get_all_volumes():
    volumes_dict = {}
    for reg in regions:
        print(f"\rAnalysing region '{reg}'...", end='')

        ec2 = regions_clients[reg]
        volumes = list(ec2.volumes.all())

        if len(volumes) > 0:
            volumes_dict[reg] = {}
        else:
            continue
        for volume in volumes:
            volumes_dict[reg][volume.id] = {"volume": volume}  # TODO this does not need to be a dict
    print("\r...Got all volumes")
    return volumes_dict


def volumes_pretty_print(volumes):
    def get_volume_array(volume_entry):
        volume = volume_entry['volume']
        # For creation date, we should parse as datetime and then strftime("%m/%d/%Y, %H:%M:%S")
        return np.array(
            [volume.create_time.strftime("%m/%d/%Y, %H:%M:%S"), volume.id, volume.iops, volume.volume_type, volume.size])

    for region in volumes.keys():
        print(f"{region}:")
        headers = np.array(["Creation Date", "ID", "IOPS", "Type", "Size"])
        data = np.array(list(map(get_volume_array, volumes[region].values())))
        width = np_len(np.append(headers.reshape(1, -1), data, axis=0)).max(axis=0)
        tp.table(data, headers, width=width)


def delete_decision(instance, region, all_metrics, cpu_max_threshold, network_threshold):
    day_period = 24 * 3600
    hour_period = 3600
    cpu_metric = next((x['value'] for x in all_metrics if x['name'] == 'CPUUtilization'), None)
    network_in_metric = next((x['value'] for x in all_metrics if x['name'] == 'NetworkIn'), None)
    network_out_metric = next((x['value'] for x in all_metrics if x['name'] == 'NetworkOut'), None)
    watch_client = regions_cloudwatches[region]

    if instance.state['Name'] == 'stopped':
        return True, "Instance is stopped", None, None

    if cpu_metric:
        cpu_day = metric_for_instance(day_period, cpu_metric, instance.id, watch_client)
        if cpu_day['Maximum'] < cpu_max_threshold:
            return True, f"CPU Usage below {cpu_max_threshold}% over last 24 hours", cpu_metric, day_period
        cpu_hour = metric_for_instance(hour_period, cpu_metric, instance.id, watch_client)
        if cpu_hour['Maximum'] < cpu_max_threshold:
            return True, f"CPU Usage below {cpu_max_threshold}% over last hour", cpu_metric, hour_period

    if network_in_metric:
        network_in_day = metric_for_instance(day_period, network_in_metric, instance.id, watch_client)
        if network_in_day['Maximum'] < network_threshold:
            return True, f"Network in below {network_threshold} bytes over last 24 hours", network_in_metric, day_period
        network_in_hour = metric_for_instance(hour_period, network_in_metric, instance.id, watch_client)
        if network_in_hour['Maximum'] < network_threshold:
            return True, f"Network in below {network_threshold} bytes over last hour", network_in_metric, hour_period

    if network_out_metric:
        network_out_day = metric_for_instance(day_period, network_out_metric, instance.id, watch_client)
        if network_out_day['Maximum'] < network_threshold:
            return True, f"Network out below {network_threshold} bytes over last 24 hours", network_out_metric, day_period
        network_out_hour = metric_for_instance(hour_period, network_out_metric, instance.id, watch_client)
        if network_out_hour['Maximum'] < network_threshold:
            return True, f"Network out below {network_threshold} bytes over last hour", network_out_metric, hour_period

    return False, "", None, None


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
        {'name': "View metrics", 'value': 'm'},
        {'name': "View images", 'value': 'i'},
        {'name': "View volumes", 'value': 'v'},
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
        print("We will check the specified criterias for periods of 1 day and 1 hour with decreasing priority")
        criterias = [{
            'type': 'list',
            'name': 'cpu',
            'message': 'What max CPU threshold do you want to use?',
            'choices': [
                {'name': '< 0 %', 'value': 0.0001},
                {'name': '< 1 %', 'value': 1},
                {'name': '< 5 %', 'value': 5},
                {'name': '< 10 %', 'value': 10},
                {'name': '< 20 %', 'value': 20},
            ]
        }, {
            'type': 'list',
            'name': 'network',
            'message': 'What network threshold do you want to use?',
            'choices': [
                {'name': '< 500 bytes', 'value': 500},
                {'name': '< 100 kbytes', 'value': 100e3},
                {'name': '< 1 Mbytes', 'value': 1e6},
                {'name': '< 10 Mbytes', 'value': 10e6},
            ]
        }]

        answers = prompt(criterias)

        instances_to_delete = []
        normal_instances = []
        for region in all_instances.keys():
            for instance_id in all_instances[region].keys():
                instance = all_instances[region][instance_id]['instance']
                if instance.state['Name'] in ['shutting-down', 'terminated']:
                    continue
                delete = delete_decision(instance, region, all_metrics, answers['cpu'], answers['network'])
                if delete[0]:
                    instances_to_delete.append({'name': f"{region}: {instance_id} => {delete[1]}",
                                                'value': {'region': region, 'id': instance_id, 'metric': delete[2], 'period': delete[3]}})
                else:
                    normal_instances.append({'name': f"{region}: {instance_id}",
                                             'value': {'region': region, 'id': instance_id}})

        to_delete_questions = [{
            'type': 'list',
            'name': 'instance',
            'message': 'What instance do you want to delete?',
            'choices': instances_to_delete + [Separator()] + normal_instances + [Separator(), {'name': "Don't delete anything", 'value': None}]
        }]
        answers = prompt(to_delete_questions)

        if 'instance' in answers:
            instance = answers['instance']
            confirmation_question = [{
                'type': 'confirm',
                'message': f"Are you sure you want to delete instance {instance['id']}?",
                'name': 'delete',
                'default': True,
            }]
            confirmation = prompt(confirmation_question)

            if confirmation['delete']:
                print("Deleting instance...")
                delete_instance(instance['id'], instance['region'])
                print("...Done")
        pass
    elif key == 'm':
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
    elif key == 'i':
        # get other resources types
        images = get_all_images()
        images_pretty_print(images)
        pass
    elif key == 'v':
        volumes = get_all_volumes()
        volumes_pretty_print(volumes)
    else:
        print("Unsupported operation")

print("Bye")
