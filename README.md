# AWS Exterminator

AWS Exterminator is a command-line tool to help you discover and delete unused instances, EBS volumes and AMI images across all regions in your AWS account. The program will suggest resources to delete based on metrics returned by CloudWatch.

By default, the metrics for an instance will be the average CPU and network usage over the last week and the program will suggest deleting instances that fall below a treshold for these metrics.

The user will be able to request  the retrieval of more metrics for the instances as well as manually select instances to delete.

## Program flow

1. The user chooses to retrieve instances, volumes or images
   1. The program will retrieve all resources from the type across regions and their respective metrics
   2. The program will list all resources and the metrics and flag suggested unused instances
   3. Then the user can decide to delete suggested resources, select resources to delete or request more metrics
2. The user can quit the program, refresh or change resource type

## How to run

You need to create a file named `.env` in the root folder of the project, containing:

```
AWS_ACCESS_KEY_ID=<accesskey>
AWS_SECRET_ACCESS_KEY=<secretkey>
AWS_DEFAULT_REGION=<defaultregion>
```

The default region is required by the AWS sdk but the program will check every AWS region anyway.

The program is written in Python 3.

Then, you can install the requirements present in `requirements.txt` by using `pip`:

```
pip install -r requirements.txt
```

And finally launch the program:

```
python exterminator.py
```

Then you can follow the on-screen instructions to use the program.