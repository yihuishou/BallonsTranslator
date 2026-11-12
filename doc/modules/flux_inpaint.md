# FLUX inpainting

Read this before changing the local FLUX inpainter, its model list, or the
latent-blending pipeline.

## Ownership

| Concern | Owner |
| --- | --- |
| Registration, parameters, download list, and image blending | [`inpaint_default.py`](../../ballontranslator/modules/inpaint/inpaint_default.py) |
| Denoising loop, mask packing, and VAE decoding | [`flux_inpaint_pipeline.py`](../../ballontranslator/modules/inpaint/flux_inpaint_pipeline.py) |
| Whole-image vs per-block dispatch | [`base.py`](../../ballontranslator/modules/inpaint/base.py) |
| Module selection and model download prompts | [`module_manager.py`](../../ballontranslator/ui/module_manager.py) |

The registered key is `flux2-klein`. `inpaint_by_block = False`, so the module
receives the whole page and a page-sized mask instead of per-block crops.

## Loading

`Flux2Klein._load_model()` builds four pieces and keeps only `pipeline`
(`_load_model_keys = {'pipeline'}`):

1. Transformer from `data/models/flux-2-klein-4b-Q4_K_M.gguf` through
   `Flux2Transformer2DModel.from_single_file()` with
   `GGUFQuantizationConfig(compute_dtype=torch.bfloat16)`. The architecture comes
   from `data/models/flux-2-klein-4b/transformer/config.json`.
2. Prompt embeddings from `data/models/flux2_inpaint_prompt.safetensors`
   (key `prompt_embeds`) as bf16. Because the prompt vector is precomputed, the
   pipeline is constructed with `text_encoder=None, tokenizer=None`: no text
   encoder is downloaded, loaded, or run, and the module exposes no prompt
   parameter.
3. VAE from `data/models/flux-2-vae` (`AutoencoderKLFlux2`, bf16).
4. `Flux2KleinInpaintPipeline.from_pretrained('data/models/flux-2-klein-4b',
   local_files_only=True)` for `model_index.json` and the scheduler config.

`updateParam('device')` moves the already-loaded pipeline; nothing is reloaded.
Parameters: `model` (single option `4b-Q4_K_M`), `max_resolution`
(512/768/1024/1280/1536/2048, default 1024), `device`, and `step` (default 8,
not exposed in the config UI).

## Inference

`_inpaint()` thresholds the mask at 127, shrinks the long edge to
`max_resolution` (never upscales), rounds both sides to a multiple of 16, and
resizes image and mask with `smart_resize`. It then calls the pipeline with
`prompt_embeds`, the resized `height`/`width`, `num_inference_steps=step`,
`guidance_scale=1`, and `output_type='numpy'`. The result is scaled back to the
original size and blended as `generated * mask + original * (1 - mask)`, so
pixels outside the mask stay bit-identical to the source image.

Inside the pipeline:

- `image` is normalised with `array / 127.5 - 1`, encoded by the VAE, packed to
  tokens, and used both as the reference stream and as the starting point:
  `latents = scale_noise(image_latents, t0, noise)`.
- The mask is interpolated to the packed spatial size and packed alongside the
  latents.
- Each step feeds `cat([latents, image_latents])` to the transformer, keeps the
  prediction for the noisy latents only, steps the scheduler, then blends
  `latents = (1 - mask) * scale_noise(image_latents, t_next, noise) + mask * latents`.
  Only tokens inside the mask can change.
- Steps run without classifier-free guidance (`guidance_scale=1`); the pipeline
  raises if CFG would be required. The distilled model's step count is the whole
  schedule.

## Model files

All paths are relative to the repository root; `download_file_list` owns them.

| Repository | Files | Destination | Checked |
| --- | --- | --- | --- |
| `black-forest-labs/FLUX.2-klein-4B` | `model_index.json`, `scheduler/scheduler_config.json`, `transformer/config.json` | `data/models/flux-2-klein-4b/` | no |
| `unsloth/FLUX.2-klein-4B-GGUF` | `flux-2-klein-4b-Q4_K_M.gguf` | `data/models/` | sha256 |
| `black-forest-labs/FLUX.2-klein-4B` | `vae/config.json`, `vae/diffusion_pytorch_model.safetensors` | `data/models/flux-2-vae/` | no / sha256 |
| `dreMaz/flux2-klein-inpaint` | `flux2_inpaint_prompt.safetensors` | `data/models/` | sha256 |

Dependencies: `torch`, `diffusers>=0.37.1`, `safetensors`,
`transformers==4.57.6`, `gguf>=0.10.0`, `accelerate>=0.26.0`, `hf_transfer`.

`flux2_inpaint_prompt.safetensors` is not a prompt text file. It holds one
precomputed `prompt_embeds` tensor produced by the FLUX.2-klein text encoder for
a fixed restoration instruction, so it is valid only for this checkpoint family
and this pipeline's text-token layout.

## FLUX.3 compatibility

FLUX.3 Image Klein cannot reuse any of this:

- The prompt file is bound to FLUX.2's text encoder output space. FLUX.3 uses
  Qwen3-VL-4B-Instruct, stacks hidden states from eight of its 36 layers
  (4, 8, 12, 16, 20, 24, 28, 32) into 20480 dimensions, projects to the
  transformer width, and pads prompts to a multiple of 80 tokens. Dimensions,
  sequence length, and semantics all differ.
- The denoiser differs: `Flux3Transformer2DModel` runs five per-stream blocks
  for text, noisy image, and reference separately, then 28 joint blocks, with
  RoPE over `t/h/w/l`. FLUX.3 ships as a `ModularPipeline` with
  `modular_model_index.json`; this module loads `Flux2Transformer2DModel` from a
  GGUF file plus a FLUX.2 `model_index.json`.
- FLUX.3 editing has no mask input. It takes an instruction, up to ten reference
  images, and optional bounding boxes on a 0-1000 grid, and the boxes guide
  placement rather than constraining pixels. There is no equivalent of this
  pipeline's per-step latent blending.

The one shared piece is the VAE: FLUX.3 uses the same 32-channel, 8x-compressed,
2x2-packed autoencoder architecture as FLUX.2, so `flux-2-vae` is a candidate
substitute, though FLUX.3 ships its own `ae.safetensors`.

Supporting FLUX.3 would mean a new inpainter class and a new pipeline, not a
checkpoint swap:

1. Load FLUX.3 through `ModularPipeline.from_pretrained()` (optionally a
   quantized `Flux3Transformer2DModel.from_single_file()` with
   `BFLQuantizationConfig`), keeping its own text encoder and `ae`.
2. Recompute prompt embeddings with Qwen3-VL and the eight-layer projection if a
   fixed instruction is wanted; FLUX.3 expects full scene captions and the
   official pipeline relies on prompt upsampling, so a frozen embedding is a
   quality risk.
3. Reimplement mask conditioning by hand: FLUX.3 has no mask parameter, so the
   blending loop above would have to be reproduced against its transformer and
   latent layout.

## Verification

No unit test covers this module: the weights are multi-gigabyte and the
inference needs a GPU. Changes are verified by selecting `flux2-klein` in the
module manager, letting it download or validate the files (the three sha256
entries are checked), and running inpaint on one page. Check the log for the
chosen `max_resolution` before blaming the model for soft results: pages larger
than that are downscaled, generated, and upscaled again.
