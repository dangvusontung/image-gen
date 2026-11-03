"""Optional hairstyle direction for creating a new character master."""
from typing import Literal

HairStyle = Literal['reference', 'straight', 'waves', 'bob', 'pixie', 'ponytail', 'bun', 'braids', 'custom']
HAIRSTYLES = {
    'straight': 'long straight hair with a natural center part',
    'waves': 'loose shoulder-length waves with a soft side part',
    'bob': 'a sleek chin-length bob with softly curved ends',
    'pixie': 'a short textured pixie cut with soft layers',
    'ponytail': 'a high ponytail with a neatly gathered crown',
    'bun': 'a relaxed low bun with soft face-framing strands',
    'braids': 'two neatly woven braids with a natural center part',
}


def hairstyle_direction(style: HairStyle, custom: str) -> str:
    if style == 'reference':
        return ''
    description = custom.strip() if style == 'custom' else HAIRSTYLES[style]
    return (
        '\n\nCHARACTER HAIRSTYLE OVERRIDE: Replace only the reference hairstyle with the following hair design: '
        f'{description}. '
        'This hair direction takes precedence over instructions to preserve the reference hairstyle. '
        'Preserve the original hair color unless a different hair color is explicitly requested here. '
        'Preserve facial identity, apparent age, facial geometry, skin tone, body proportions, outfit and rendering style. '
        'Apply this hairstyle consistently to the single character; keep the face recognizable.'
    )
