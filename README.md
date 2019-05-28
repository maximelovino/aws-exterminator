# AWS Exterminator

AWS Exterminator is a command-line tool to help you discover and delete unused instances, EBS volumes and AMI images across all regions in your AWS account. The program will suggest resources to delete based on metrics returned by CloudWatch.

## Demonstration

![](demo.gif)

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