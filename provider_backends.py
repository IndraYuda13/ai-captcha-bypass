import base64
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests
from openai import OpenAI
from google import genai
from google.genai import types


def _image_to_base64(image_path: str) -> str:
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def _run_cli(command: list[str], stdin_text: Optional[str] = None) -> str:
    result = subprocess.run(
        command,
        input=stdin_text,
        text=True,
        capture_output=True,
        check=True,
    )
    return (result.stdout or '').strip()


class ProviderBackend:
    def generate_text_from_image(self, prompt: str, image_path: str, model: Optional[str] = None) -> str:
        raise NotImplementedError

    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        raise NotImplementedError

    def transcribe_audio(self, prompt: str, audio_path: str, model: Optional[str] = None) -> str:
        raise NotImplementedError


class OpenAIBackend(ProviderBackend):
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def generate_text_from_image(self, prompt: str, image_path: str, model: Optional[str] = None) -> str:
        model_to_use = model or 'gpt-4o'
        base64_image = _image_to_base64(image_path)
        response = self.client.chat.completions.create(
            model=model_to_use,
            messages=[
                {'role': 'user', 'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{base64_image}'}}
                ]}
            ],
            temperature=0,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()

    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        model_to_use = model or 'gpt-4o'
        response = self.client.chat.completions.create(
            model=model_to_use,
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()

    def transcribe_audio(self, prompt: str, audio_path: str, model: Optional[str] = None) -> str:
        model_to_use = model or 'gpt-4o-transcribe'
        with open(audio_path, 'rb') as audio_file:
            response = self.client.audio.transcriptions.create(model=model_to_use, file=audio_file, prompt=prompt)
        return response.text.strip()


class GeminiBackend(ProviderBackend):
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv('GOOGLE_API_KEY'))

    def generate_text_from_image(self, prompt: str, image_path: str, model: Optional[str] = None) -> str:
        model_to_use = model or 'gemini-2.5-pro'
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
        response = self.client.models.generate_content(
            model=model_to_use,
            contents=[types.Part.from_bytes(data=image_bytes, mime_type='image/png'), prompt],
        )
        return (response.text or '').strip()

    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        model_to_use = model or 'gemini-2.5-pro'
        response = self.client.models.generate_content(model=model_to_use, contents=[prompt])
        return (response.text or '').strip()

    def transcribe_audio(self, prompt: str, audio_path: str, model: Optional[str] = None) -> str:
        model_to_use = model or 'gemini-2.5-pro'
        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type='audio/mpeg')
        response = self.client.models.generate_content(
            model=model_to_use,
            config=types.GenerateContentConfig(system_instruction=prompt),
            contents=['Transcribe the captcha from the audio file.', audio_part],
        )
        return (response.text or '').strip()


class GeminiCliBackend(ProviderBackend):
    def __init__(self):
        self.command = os.getenv('GEMINI_CLI_COMMAND', 'gemini')

    def generate_text_from_image(self, prompt: str, image_path: str, model: Optional[str] = None) -> str:
        cmd = [self.command]
        if model:
            cmd += ['--model', model]
        cmd += ['-p', prompt, image_path]
        return _run_cli(cmd)

    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        cmd = [self.command]
        if model:
            cmd += ['--model', model]
        cmd += ['-p', prompt]
        return _run_cli(cmd)

    def transcribe_audio(self, prompt: str, audio_path: str, model: Optional[str] = None) -> str:
        cmd = [self.command]
        if model:
            cmd += ['--model', model]
        cmd += ['-p', prompt, audio_path]
        return _run_cli(cmd)


class CodexCliBackend(ProviderBackend):
    def __init__(self):
        self.command = os.getenv('CODEX_CLI_COMMAND', 'codex')

    def generate_text_from_image(self, prompt: str, image_path: str, model: Optional[str] = None) -> str:
        cmd = [self.command, 'exec']
        if model:
            cmd += ['--model', model]
        cmd += [f'{prompt}\n\nImage path: {image_path}']
        return _run_cli(cmd)

    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        cmd = [self.command, 'exec']
        if model:
            cmd += ['--model', model]
        cmd += [prompt]
        return _run_cli(cmd)

    def transcribe_audio(self, prompt: str, audio_path: str, model: Optional[str] = None) -> str:
        cmd = [self.command, 'exec']
        if model:
            cmd += ['--model', model]
        cmd += [f'{prompt}\n\nAudio path: {audio_path}']
        return _run_cli(cmd)


class CustomRelayBackend(ProviderBackend):
    def __init__(self):
        self.base_url = os.getenv('CUSTOM_LMM_BASE_URL', '').rstrip('/')
        self.api_key = os.getenv('CUSTOM_LMM_API_KEY', '')
        self.default_model = os.getenv('CUSTOM_LMM_MODEL', 'gpt-5.4')
        if not self.base_url:
            raise ValueError('CUSTOM_LMM_BASE_URL is required for provider=custom')

    def _post(self, payload: dict) -> str:
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        response = requests.post(self.base_url, headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            for key in ('output_text', 'text', 'content', 'response'):
                if isinstance(data.get(key), str):
                    return data[key].strip()
        return json.dumps(data)

    def generate_text_from_image(self, prompt: str, image_path: str, model: Optional[str] = None) -> str:
        return self._post({
            'model': model or self.default_model,
            'prompt': prompt,
            'image_path': image_path,
            'mode': 'vision'
        })

    def generate_text(self, prompt: str, model: Optional[str] = None) -> str:
        return self._post({
            'model': model or self.default_model,
            'prompt': prompt,
            'mode': 'text'
        })

    def transcribe_audio(self, prompt: str, audio_path: str, model: Optional[str] = None) -> str:
        return self._post({
            'model': model or self.default_model,
            'prompt': prompt,
            'audio_path': audio_path,
            'mode': 'audio'
        })


def get_backend(provider: str) -> ProviderBackend:
    provider = provider.lower()
    if provider == 'openai':
        return OpenAIBackend()
    if provider == 'gemini':
        return GeminiBackend()
    if provider == 'gemini-cli':
        return GeminiCliBackend()
    if provider == 'codex':
        return CodexCliBackend()
    if provider == 'custom':
        return CustomRelayBackend()
    raise ValueError(f'Unsupported provider: {provider}')
