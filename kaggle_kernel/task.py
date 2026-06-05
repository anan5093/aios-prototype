import os
import subprocess
import time
import torch

def run_task():
    print("=== System Verification ===")
    if torch.cuda.is_available():
        print(f"✅ Active GPU Verified: {torch.cuda.get_device_name(0)}")
    else:
        print("❌ Critical Alert: GPU driver unlinked. Terminating script.")
        return

    # Configuration Constants
    NGROK_AUTH_TOKEN = "3EgV9w6ylxoBs067IbovSmpfjSv_eD4BhXJXRZ6w9rkgKVdx" 
    MODEL_NAME = "llama3"
    OLLAMA_PORT = 11434

    print("=== Installing Python dependencies ===")
    subprocess.run("pip install pyngrok -q", shell=True, check=True)
    from pyngrok import ngrok

    print("=== Deploying Ollama Environment ===")
    # Install zstd (required by newer Ollama install scripts for extraction)
    subprocess.run("apt-get update && apt-get install -y zstd", shell=True, check=True)
    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)

    print("=== Initializing Local Instance Pipeline ===")
    os.environ["OLLAMA_HOST"] = f"0.0.0.0:{OLLAMA_PORT}"
    ollama_proc = subprocess.Popen(["ollama", "serve"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(6) # Safe buffer for network handshake

    print(f"=== Downloading Weights: {MODEL_NAME} ===")
    subprocess.run(f"ollama pull {MODEL_NAME}", shell=True, check=True)

    print("=== Creating Encrypted Ngrok Gateway ===")
    ngrok.set_auth_token(NGROK_AUTH_TOKEN)
    tunnel = ngrok.connect(OLLAMA_PORT, "http")
    
    print("\n" + "🚀" * 20)
    print(f"KAGGLE BENCHMARK ACTIVE URL: {tunnel.public_url}")
    print("🚀" * 20 + "\n")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("Safely disconnecting endpoints...")
        ngrok.disconnect(tunnel.public_url)
        ollama_proc.terminate()

if __name__ == "__main__":
    run_task()
