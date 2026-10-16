# emaki

Official SDK for emaki (emaki.ai), the Japanese-language AI video generator for Seedance 2.5 and Seedance 2.0.

This is the Python client for [emaki](https://emaki.ai/?utm_source=pypi&utm_medium=package). One API key runs [Seedance 2.5](https://emaki.ai/seedance-2-5), [Seedance 2.0](https://emaki.ai/seedance-2) and the other video and image models on the site, on your own credits.

日本語での使い方は [シーダンス](https://emaki.ai/) へ。

```bash
pip install emaki
```

```python
from emaki import generate_video, generate_image

clip = generate_video("a paper boat drifting down a rain gutter, low angle, slow push-in")
pic = generate_image("a paper-cut layered mountain range at dusk, warm rim light", aspect_ratio="16:9")
```

Standard library only, no dependencies. Each call waits for the run and returns the URL of the finished file.

## API key

Sign in on [emaki.ai](https://emaki.ai/?utm_source=pypi&utm_medium=package), create a key at [emaki.ai/settings/apikeys](https://emaki.ai/settings/apikeys), then pass it as `api_key=` or export it:

```bash
export EMAKI_API_KEY=sk-...
```

A key runs on your account exactly like the site does. Every run costs credits on your emaki account, the same price as on the website.

```python
from emaki import credits
print(credits())  # remaining credits, free to call
```

## Video

```python
generate_video("a fox trotting through fresh snow at dawn, tracking shot",
               duration=8, resolution="720p", aspect_ratio="9:16")

# image to video: the image becomes the first frame
generate_video("the camera slowly orbits the statue", image="https://example.com/statue.jpg")

# another model
generate_video("a street drummer in the rain", model="seedance_2_fast")
```

The default model is `seedance_2_5`. Other ids: `seedance_2`, `seedance_2_fast`, `seedance_2_mini`, `minimax_h3`, `veo_3_1`. Any extra keyword argument is sent in `parameters` as it is (`duration`, `resolution`, `aspect_ratio`, `generate_audio`, `image`, `last_frame_image`; Veo 3.1 takes `aspectRatio`).

Turning a still into a clip on the site works the same way: see [image to video](https://emaki.ai/image-to-video). To sharpen a finished clip there is the [AI video upscaler](https://emaki.ai/video-upscaler).

## Images

```python
generate_image("isometric diorama of a ramen shop at night", aspect_ratio="1:1")
generate_image("product shot of a glass perfume bottle on wet slate", model="gpt_image_2", resolution="2K")
```

The default model is `nano_banana_2_lite`. Other ids: `nano_banana_2`, `seedream_5_lite`, `gpt_image_2`.

## Submit now, collect later

```python
from emaki import submit, status, wait

run_id = submit("a lighthouse in a storm, waves crashing", "seedance_2_5", duration=5)
print(status(run_id)["status"])   # generating | completed | failed
url = wait(run_id)                # polls every 5 seconds, 15 minutes by default
```

## Errors worth catching

Each failure is its own subclass of `EmakiError`, so you can branch on what to do next:

- `AuthError`: no key, or the key is wrong or deleted
- `QuotaError`: the account is out of credits
- `PlanError`: that model needs a purchase on the account first
- `BusyError`: another run on this account is still generating
- `RejectedError`: the content filter refused the prompt, or a cooldown is active; reword it
- `GenerationFailed`: the run was accepted but failed; `.code` holds the failure code

Any other refusal raises `EmakiError` with the server's message, for example a parameter out of range.

MIT licensed. Made by [emaki](https://emaki.ai/?utm_source=pypi&utm_medium=package).
