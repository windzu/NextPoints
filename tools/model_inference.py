import requests


def call_remote_inference(scene_name, INFERENCE_SERVER_URL, INFERENCE_ENDPOINT):
    """调用远程推理服务"""
    try:
        # 准备发送到推理服务器的数据
        inference_url = f"{INFERENCE_SERVER_URL}{INFERENCE_ENDPOINT}"

        # 方案1: 发送scene_name（如果推理服务器可以访问相同的文件系统）
        payload = {
            "scene_name": scene_name,
        }

        print(f"Sending inference request to: {inference_url}")

        # 发送POST请求到推理服务器
        response = requests.post(
            inference_url,
            json=payload,
            timeout=300,  # 5分钟超时
            headers={"Content-Type": "application/json"},
        )

        if response.status_code == 200:
            result = response.json()
            # 检查业务逻辑是否成功
            if result.get("success", False):
                print("Inference completed successfully!")
                message = result.get("message", "No message provided")
                return {
                    "success": True,
                    "message": message,
                }
            else:
                # 服务返回success=False的情况
                error_msg = result.get("error", "Unknown error from inference server")
                print(f"Inference failed: {error_msg}")
                return {"success": False, "error": error_msg}
        else:
            # HTTP状态码不是200的情况（如400, 500等）
            result = response.json()
            error_msg = result.get("error", f"HTTP {response.status_code} error")
            print(f"Inference server error: {response.status_code}, {error_msg}")
            return {
                "success": False,
                "error": f"Inference server error: {error_msg}",
            }

    except requests.exceptions.Timeout:
        print("Inference request timeout")
        return {"success": False, "error": "推理服务超时"}

    except requests.exceptions.ConnectionError:
        print("Cannot connect to inference server")
        return {"success": False, "error": "无法连接到推理服务器"}

    except Exception as e:
        print(f"Error calling remote inference: {str(e)}")
        return {"success": False, "error": f"推理服务调用失败: {str(e)}"}
