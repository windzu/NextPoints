import boto3
from botocore.exceptions import ClientError, NoCredentialsError,EndpointConnectionError
from typing import List, Dict, Optional, Tuple
import os
import re
import logging
import json
from typing import Any

logger = logging.getLogger(__name__)


class S3Service:
    """S3 存储服务类"""
    
    def __init__(self, access_key_id: str, secret_access_key: str, 
                 endpoint_url: Optional[str] = None, region_name: str = "us-east-1"):
        """
        初始化 S3 客户端
        
        Args:
            access_key_id: AWS Access Key ID
            secret_access_key: AWS Secret Access Key
            endpoint_url: S3 端点 URL（可选，用于兼容 MinIO 等）
            region_name: AWS 区域名称
        """
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                endpoint_url=endpoint_url,
                region_name=region_name
            )
            self.region_name = region_name
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
    def test_connection(self, bucket_name: str) -> Tuple[bool, str]:
        """
        测试 S3 连接和存储桶访问权限
        
        Args:
            bucket_name: 存储桶名称
            
        Returns:
            (成功标志, 错误信息)
        """
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
            return True, "Connection successful"
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False, f"Bucket '{bucket_name}' not found"
            elif error_code == '403':
                return False, f"Access denied to bucket '{bucket_name}'"
            else:
                return False, f"Error accessing bucket: {e}"
        except NoCredentialsError:
            return False, "Invalid credentials"
        except Exception as e:
            return False, f"Connection error: {e}"
    
    def object_exists(self, bucket: str, key: str, *, version_id: Optional[str] = None) -> bool:
        """
        判断指定对象是否存在（精确到对象，不是前缀）。
        存在 -> True；不存在 -> False；权限/网络等异常 -> 抛出异常。

        Args:
            bucket: 桶名
            key: 对象键（不要以'/'开头，S3允许但不推荐）
            version_id: 开启版本控制时，指定版本检查（可选）
        """
        try:
            kwargs = {"Bucket": bucket, "Key": key.lstrip("/")}
            if version_id:
                kwargs["VersionId"] = version_id
            self.s3_client.head_object(**kwargs)
            return True
        except ClientError as e:
            # 典型不存在：HTTP 404 或 Error Code 为 '404'/'NoSuchKey'/'NotFound'
            code = str(e.response.get("Error", {}).get("Code", ""))
            status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if code in ("404", "NoSuchKey", "NotFound") or status == 404:
                return False
            # 其他错误（403/网络/区域等）交由调用方处理
            raise
        except EndpointConnectionError:
            # 端点连不通（MinIO/S3 网络问题）
            raise

    def list_objects(self, bucket_name: str, prefix: str = "") -> List[Dict]:
        """
        列出存储桶中的对象
        
        Args:
            bucket_name: 存储桶名称
            prefix: 对象键前缀
            
        Returns:
            对象列表，每个对象包含 key, size, last_modified 等信息
        """
        try:
            objects = []
            paginator = self.s3_client.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        objects.append({
                            'key': obj['Key'],
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'etag': obj['ETag']
                        })
            
            return objects
        except Exception as e:
            logger.error(f"Failed to list objects: {e}")
            raise

    def list_all_objects(self, bucket_name: str, prefix: str) -> List[Dict]:
        """
        列出存储桶中指定前缀下的所有对象。
        (Lists all objects under a given prefix in a bucket.)
        """
        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        all_objects = []
        for page in pages:
            if "Contents" in page:
                all_objects.extend(page['Contents'])
        return all_objects
    
    def read_json_object(self, bucket_name: str, key: str) -> Dict:
        """
        从 S3 读取并解析一个 JSON 文件。
        (Reads and parses a JSON file from S3.)
        """
        try:
            response = self.s3_client.get_object(Bucket=bucket_name, Key=key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except Exception as e:
            print(f"Error reading JSON object s3://{bucket_name}/{key}: {e}")
            raise
    
    def upload_json_object(self, bucket_name: str, key: str, data_dict: Dict[str, Any]):
        """
        将一个 Python 字典序列化为 JSON 并上传到 S3。
        """
        try:
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=json.dumps(data_dict, indent=2), # indent for human readability
                ContentType='application/json'
            )
        except ClientError as e:
            print(f"Error uploading JSON object to s3://{bucket_name}/{key}: {e}")
            raise

    def generate_presigned_url(self, bucket_name: str, object_key: str, 
                         expiration: int = 3600) -> str:
        """
        生成预签名 URL
        
        Args:
            bucket_name: 存储桶名称
            object_key: 对象键
            expiration: 过期时间（秒）
            
        Returns:
            预签名 URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise
    
    def get_batch_presigned_urls(self, bucket_name: str, object_keys: List[str], 
                                expiration: int = 3600) -> Dict[str, str]:
        """
        批量生成预签名 URL
        
        Args:
            bucket_name: 存储桶名称
            object_keys: 对象键列表
            expiration: 过期时间（秒）
            
        Returns:
            对象键到预签名URL的映射
        """
        try:
            urls = {}
            for object_key in object_keys:
                if object_key:  # 确保object_key不为空
                    urls[object_key] = self.generate_presigned_url(bucket_name, object_key, expiration)
            return urls
        except Exception as e:
            logger.error(f"Failed to generate batch presigned URLs: {e}")
            raise
    
    def get_object_url(self, bucket_name: str, object_key: str, 
                      use_presigned: bool = False, expiration: int = 3600) -> str:
        """
        获取对象访问 URL
        
        Args:
            bucket_name: 存储桶名称
            object_key: 对象键
            use_presigned: 是否使用预签名 URL
            expiration: 预签名 URL 过期时间（秒）
            
        Returns:
            对象访问 URL
        """
        if use_presigned:
            return self.generate_presigned_url(bucket_name, object_key, expiration)
        else:
            # 构建直接访问 URL
            if hasattr(self.s3_client, '_endpoint') and self.s3_client._endpoint.host:
                base_url = self.s3_client._endpoint.host
                return f"{base_url}/{bucket_name}/{object_key}"
            else:
                return f"https://{bucket_name}.s3.{self.region_name}.amazonaws.com/{object_key}"
    
    def sync_project_data(self, bucket_name: str, bucket_prefix: str = "") -> List[Dict]:
        """
        同步项目数据，解析 S3 中的文件结构
        
        Args:
            bucket_name: 存储桶名称
            bucket_prefix: 存储桶前缀
            
        Returns:
            解析后的帧数据列表
        """
        try:
            objects = self.list_objects(bucket_name, bucket_prefix)
            frames_data = []
            
            # 按文件类型分组
            pointcloud_files = {}
            image_files = {}
            pose_files = {}
            
            # 正则表达式匹配时间戳
            timestamp_pattern = r'(\d{10,})' # 匹配10位以上的数字作为时间戳
            
            for obj in objects:
                key = obj['key']
                
                # 提取时间戳
                timestamp_match = re.search(timestamp_pattern, os.path.basename(key))
                if not timestamp_match:
                    continue
                    
                timestamp_str = timestamp_match.group(1)
                
                # 根据文件扩展名分类
                if key.endswith(('.pcd', '.bin', '.ply')):
                    pointcloud_files[timestamp_str] = key
                elif key.endswith(('.jpg', '.jpeg', '.png')):
                    # 提取相机ID（假设文件名包含相机标识）
                    camera_id = self._extract_camera_id(key)
                    if timestamp_str not in image_files:
                        image_files[timestamp_str] = {}
                    image_files[timestamp_str][camera_id] = key
                elif key.endswith('.json') and 'pose' in key.lower():
                    pose_files[timestamp_str] = key
            
            # 构建帧数据
            for timestamp_ns, pointcloud_key in pointcloud_files.items():
                
                frame_data = {
                    'timestamp_ns': timestamp_ns,
                    'pointcloud_s3_key': pointcloud_key,
                    'images': image_files.get(timestamp_ns, {}),
                    'pose_s3_key': pose_files.get(timestamp_ns)
                }
                
                frames_data.append(frame_data)
            
            # 按时间戳排序
            frames_data.sort(key=lambda x: x['timestamp_ns'])
            
            logger.info(f"Synced {len(frames_data)} frames from S3")
            return frames_data
            
        except Exception as e:
            logger.error(f"Failed to sync project data: {e}")
            raise
    
    def _extract_camera_id(self, file_path: str) -> str:
        """
        从文件路径中提取相机ID
        
        Args:
            file_path: 文件路径
            
        Returns:
            相机ID
        """
        # 简单的相机ID提取逻辑，可根据实际文件命名规则调整
        basename = os.path.basename(file_path)
        
        # 常见的相机ID模式
        camera_patterns = [
            r'cam_?(\d+)',
            r'camera_?(\d+)', 
            r'front|back|left|right',
            r'(front_left|front_right|back_left|back_right)'
        ]
        
        for pattern in camera_patterns:
            match = re.search(pattern, basename.lower())
            if match:
                return match.group(1) if match.groups() else match.group(0)
        
        return "default"