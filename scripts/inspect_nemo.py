import torch
import nemo.collections.asr as nemo_asr
from omegaconf import OmegaConf

def inspect():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading model on {device}...")
    model = nemo_asr.models.ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v2")
    model = model.to(device).eval()
    
    print("\n--- Config Keys ---")
    print(model.cfg.keys())
    
    if 'test_ds' in model.cfg:
        print("\n--- test_ds Config ---")
        print(OmegaConf.to_yaml(model.cfg.test_ds))
        
    if 'transcribe' in model.cfg:
         print("\n--- transcribe Config ---")
         print(OmegaConf.to_yaml(model.cfg.transcribe))

if __name__ == "__main__":
    inspect()
