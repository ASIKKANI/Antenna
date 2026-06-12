# Built-in Pixel Pets with State-Based Animations
# Represents 16x16 grids using a compact character map.
from typing import Dict, List

PALETTES = {
    "cat": {
        ".": "",           # transparent
        "B": "#0f172a",    # dark outline
        "W": "#f8fafc",    # white fur
        "O": "#f97316",    # orange accents
        "P": "#fda4af",    # pink ears/blush
        "G": "#64748b",    # gray shading
        "Y": "#eab308"     # yellow eyes
    },
    "dog": {
        ".": "",           # transparent
        "B": "#0f172a",    # dark outline
        "C": "#d97706",    # brown fur
        "W": "#fef3c7",    # light tan fur
        "R": "#ef4444",    # red collar/tongue
        "P": "#f472b6",    # pink nose
        "Y": "#facc15"     # tag
    },
    "slime": {
        ".": "",           # transparent
        "B": "#0f172a",    # dark outline
        "S": "#38bdf8",    # sky blue body
        "G": "#0284c7",    # dark blue shadow
        "W": "#ffffff",    # highlight
        "P": "#fda4af"     # blush
    }
}

RAW_ANIMATIONS = {
    "cat": {
        "idle_loop": {
            "speed_ms": 600,
            "frames": [
                [
                    "................",
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.....",
                    "...BGGGGGGGB....",
                    "..BGGGGGGGGGB...",
                    "..BGGGGGGGGGB...",
                    "...BBBBBBBBB....",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.B...",
                    "...BGGGGGGBB....",
                    "..BGGGGGGGBB....",
                    "..BGGGGGGGB.....",
                    "...BBBBBBB......",
                    "................",
                    "................"
                ]
            ]
        },
        "focus_mode_active": {
            "speed_ms": 300,
            "frames": [
                [
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.....",
                    "...BWWWWWWB.....",
                    "..BWWWWWWWWB....",
                    "..BWWWWWWWWB....",
                    "..BBBBBBBBBB.B..",
                    "..BB......BB.B..",
                    "................",
                    "................"
                ],
                [
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.....",
                    "...BWWWWWWB.B...",
                    "..BWWWWWWWWB.B..",
                    "..BWWWWWWWWB....",
                    "..BBBBBBBBBB....",
                    "..BB......BB....",
                    "................",
                    "................"
                ]
            ]
        },
        "nagging_mild": {
            "speed_ms": 400,
            "frames": [
                [
                    "................",
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.....",
                    "...BGGGGGGGB....",
                    "..BGGGGGGGGGB...",
                    "..BGGGGGGGGGB...",
                    "...BBBBBBBBB....",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.....",
                    "...BGGGGGGGB....",
                    "..BGGGGGGGGGB...",
                    "..BGGGGGGGGGB...",
                    "...BBBBBBBBB....",
                    "................",
                    "................"
                ]
            ]
        },
        "nagging_severe": {
            "speed_ms": 200,
            "frames": [
                [
                    "................",
                    "...B.......B....",
                    "....BWB.BWB.....",
                    "....BWWBBBWW....",
                    "...BWWWWWWWWWB..",
                    "..BWWWWWWWWWWWB.",
                    "..BWYWWWWWYWWB..",
                    "...BWWPWWPWWWB..",
                    "....BWWWWWWWB...",
                    ".....BBBBBBB....",
                    "....BGGGGGGGB...",
                    "...BGGGGGGGGGB..",
                    "...BGGGGGGGGGB..",
                    "....BBBBBBBBB...",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "....B.......B...",
                    ".....BWB.BWB....",
                    "....BWWBBBWW....",
                    "...BWWWWWWWWWB..",
                    "..BWWWWWWWWWWWB.",
                    "..BWYWWWWWYWWB..",
                    "...BWWPWWPWWWB..",
                    "....BWWWWWWWB...",
                    ".....BBBBBBB....",
                    "....BGGGGGGGB...",
                    "...BGGGGGGGGGB..",
                    "...BGGGGGGGGGB..",
                    "....BBBBBBBBB...",
                    "................",
                    "................"
                ]
            ]
        },
        "celebrating": {
            "speed_ms": 200,
            "frames": [
                [
                    "................",
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.....",
                    "...BGGGGGGGB....",
                    "..BGGGGGGGGGB...",
                    "..BGGGGGGGGGB...",
                    "...BBBBBBBBB....",
                    "................",
                    "................"
                ],
                [
                    "....B.....B.....",
                    "...BWB...BWB....",
                    "..BWWBBBBBWW...",
                    "..BWWWWWWWWWB...",
                    ".BWWWWWWWWWWWB..",
                    ".BWYWWWWWYWWB...",
                    "..BWWPWWPWWWB...",
                    "...BWWWWWWWB....",
                    "....BBBBBBB.....",
                    "...BGGGGGGGB....",
                    "..BGGGGGGGGGB...",
                    "..BGGGGGGGGGB...",
                    "...BBBBBBBBB....",
                    "................",
                    "................",
                    "................"
                ]
            ]
        }
    },
    "dog": {
        "idle_loop": {
            "speed_ms": 500,
            "frames": [
                [
                    "................",
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.....",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.B...",
                    "...BCCCCCCBB....",
                    "..BCCCCCCBB.....",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................"
                ]
            ]
        },
        "focus_mode_active": {
            "speed_ms": 300,
            "frames": [
                [
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.....",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "..BBBBBBBBB.....",
                    "..BB.....BB.....",
                    "................",
                    "................"
                ],
                [
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.B...",
                    "...BCCCCCCBB....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "..BBBBBBBB......",
                    "..BB....BB......",
                    "................",
                    "................"
                ]
            ]
        },
        "nagging_mild": {
            "speed_ms": 400,
            "frames": [
                [
                    "................",
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.....",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.....",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................"
                ]
            ]
        },
        "nagging_severe": {
            "speed_ms": 250,
            "frames": [
                [
                    "................",
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB..B..",
                    "...BCCCCCCCB.B..",
                    "....BRRRRRB.B...",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.....",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................"
                ]
            ]
        },
        "celebrating": {
            "speed_ms": 200,
            "frames": [
                [
                    "................",
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.....",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................"
                ],
                [
                    "....BB.....BB...",
                    "...BCBBBBBBCB...",
                    "..BCCCCBCCCCB...",
                    "..BCCCCCCCCB....",
                    ".BCCWCCWCCB.....",
                    ".BCCWCCWCCB.....",
                    "..BCCCPCCCB.....",
                    "...BCCCCCCCB....",
                    "....BRRRRRB.....",
                    "...BCCCCCCB.....",
                    "..BCCCCCCB......",
                    "..BCCCCCCB......",
                    "...BBBBBB.......",
                    "................",
                    "................",
                    "................"
                ]
            ]
        }
    },
    "slime": {
        "idle_loop": {
            "speed_ms": 500,
            "frames": [
                [
                    "................",
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SSSSSSSSSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "................",
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...GGGGGGGGGG...",
                    "................",
                    "................",
                    "................",
                    "................"
                ]
            ]
        },
        "focus_mode_active": {
            "speed_ms": 250,
            "frames": [
                [
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................",
                    "................"
                ]
            ]
        },
        "nagging_mild": {
            "speed_ms": 400,
            "frames": [
                [
                    "................",
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SSSSSSSSSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SSSSSSSSSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................"
                ]
            ]
        },
        "nagging_severe": {
            "speed_ms": 150,
            "frames": [
                [
                    "................",
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................",
                    "................"
                ],
                [
                    "................",
                    "................",
                    ".....SSSS.......",
                    "...SSSSSSSS.....",
                    "..SSSSSSSSSS....",
                    ".SSSSSSSSSSSS...",
                    ".SSWSSWSSSSSS...",
                    ".SSWSSWSSSSSS...",
                    ".SSSPSSSPSSSS...",
                    ".SGGGGGGGGGGS...",
                    "..SGGGGGGGGS....",
                    "...GGGGGGGG.....",
                    "................",
                    "................",
                    "................",
                    "................"
                ]
            ]
        },
        "celebrating": {
            "speed_ms": 200,
            "frames": [
                [
                    "................",
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................",
                    "................",
                    "................"
                ],
                [
                    "......SSSS......",
                    "....SSSSSSSS....",
                    "...SSSSSSSSSS...",
                    "..SSSSSSSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSWSSWSSSSSS..",
                    "..SSSPSSSPSSSS..",
                    "..SGGGGGGGGGGS..",
                    "...SGGGGGGGGS...",
                    "....GGGGGGGG....",
                    "................",
                    "................",
                    "................",
                    "................",
                    "................",
                    "................"
                ]
            ]
        }
    }
}

def expand_raw_frames(pet_type: str, raw_frames: List[List[str]]) -> List[List[str]]:
    """Expands compact char list representation into 256 hex values (16x16)."""
    palette = PALETTES.get(pet_type, {})
    expanded = []
    for frame in raw_frames:
        frame_pixels = []
        for row in frame:
            for char in row:
                frame_pixels.append(palette.get(char, ""))
        expanded.append(frame_pixels)
    return expanded

def get_premade_pets_expanded() -> List[Dict]:
    """Returns the list of premade pets expanded to full hex color arrays."""
    expanded_pets = []
    
    # 1. Add Cat
    cat_states = {}
    for state_name, state_data in RAW_ANIMATIONS["cat"].items():
        cat_states[state_name] = {
            "frames": expand_raw_frames("cat", state_data["frames"]),
            "speed_ms": state_data["speed_ms"]
        }
    expanded_pets.append({
        "id": "cat",
        "name": "Pixel Cat 🐱",
        "type": "premade",
        "states": cat_states
    })
    
    # 2. Add Dog
    dog_states = {}
    for state_name, state_data in RAW_ANIMATIONS["dog"].items():
        dog_states[state_name] = {
            "frames": expand_raw_frames("dog", state_data["frames"]),
            "speed_ms": state_data["speed_ms"]
        }
    expanded_pets.append({
        "id": "dog",
        "name": "Pixel Dog 🐶",
        "type": "premade",
        "states": dog_states
    })
    
    # 3. Add Slime
    slime_states = {}
    for state_name, state_data in RAW_ANIMATIONS["slime"].items():
        slime_states[state_name] = {
            "frames": expand_raw_frames("slime", state_data["frames"]),
            "speed_ms": state_data["speed_ms"]
        }
    expanded_pets.append({
        "id": "slime",
        "name": "Bouncy Slime 💧",
        "type": "premade",
        "states": slime_states
    })
    
    return expanded_pets
