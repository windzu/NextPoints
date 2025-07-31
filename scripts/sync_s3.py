import os
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

def sync_s3(local_directory, bucket_name, s3_prefix):
    s3 = boto3.client('s3')

    # Upload files to S3
    for root, dirs, files in os.walk(local_directory):
        for file in files:
            local_path = os.path.join(root, file)
            relative_path = os.path.relpath(local_path, local_directory)
            s3_path = os.path.join(s3_prefix, relative_path)

            try:
                s3.upload_file(local_path, bucket_name, s3_path)
                print(f'Uploaded {local_path} to s3://{bucket_name}/{s3_path}')
            except FileNotFoundError:
                print(f'File not found: {local_path}')
            except NoCredentialsError:
                print('Credentials not available for S3.')
            except PartialCredentialsError:
                print('Incomplete credentials provided for S3.')
            except Exception as e:
                print(f'Error uploading {local_path}: {e}')

    # Download files from S3
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket_name, Prefix=s3_prefix):
        for obj in page.get('Contents', []):
            s3_path = obj['Key']
            local_path = os.path.join(local_directory, os.path.relpath(s3_path, s3_prefix))

            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            try:
                s3.download_file(bucket_name, s3_path, local_path)
                print(f'Downloaded s3://{bucket_name}/{s3_path} to {local_path}')
            except FileNotFoundError:
                print(f'Local path not found for {local_path}')
            except NoCredentialsError:
                print('Credentials not available for S3.')
            except PartialCredentialsError:
                print('Incomplete credentials provided for S3.')
            except Exception as e:
                print(f'Error downloading {s3_path}: {e}')

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Sync local directory with S3 bucket.')
    parser.add_argument('--source', required=True, help='Local directory to sync')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--prefix', required=True, help='S3 prefix for the directory')

    args = parser.parse_args()

    sync_s3(args.source, args.bucket, args.prefix)