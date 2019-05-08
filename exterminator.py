import boto3
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

ec2_client = boto3.client('ec2')

response = ec2_client.describe_regions()
regions = list(map(lambda x: x['RegionName'], response['Regions']))

regions_clients = list(map(lambda region: boto3.resource('ec2', region_name=region), regions))
regions_cloudwatches = list(map(lambda region: boto3.client('cloudwatch', region_name=region), regions))

for i, client in enumerate(regions_clients):
    print("Region: ", regions[i])
    instances = client.instances.all()
    for instance in instances:
        watch = regions_cloudwatches[i]
        print("Instance of type ", instance.instance_type, " with ID: ", instance.id, " in state: ", instance.state, " / Tags: ", str(instance.tags))
        print("===========")
        print('Metrics:')
        metrics = watch.list_metrics(Namespace='AWS/EC2', Dimensions=[{"Name": "InstanceId",
                                                                       "Value": instance.id}])
        metrics = metrics['Metrics']
        for met in metrics:
            response = watch.get_metric_statistics(Namespace=met['Namespace'], MetricName=met['MetricName'], Dimensions=met['Dimensions'], Statistics=[
                'SampleCount', 'Average', 'Sum', 'Minimum', 'Maximum',
            ], Period=300, EndTime=datetime.utcnow(), StartTime=datetime.utcnow() - timedelta(seconds=600))

            data = response['Datapoints'][0]
            print(response['Label'], " => ", 'Average: ', data['Average'], ", Min: ", data['Minimum'], ', Max: ', data['Maximum'])
        print("===========")
