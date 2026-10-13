"""Internationalization support for multi-language changelog generation.

This module handles multi-language support for changelog generation. The LLM generates
content directly in the target language, but we provide section name translations and
tone guidance to ensure consistency across languages.
"""

# Section icons mapping for visual enhancement
SECTION_ICONS: dict[str, str] = {
    "breaking": "💥",
    "security": "🔒",
    "features": "✨",
    "improvements": "📈",
    "fixes": "🐛",
    "performance": "⚡",
    "deprecations": "⚠️",
    "infrastructure": "🔧",
    "docs": "📚",
    "other": "📦",
}

# Section names in different languages
# Common languages are pre-defined; the LLM handles other languages dynamically
SECTION_NAMES: dict[str, dict[str, str]] = {
    "en": {
        "breaking": "Breaking Changes",
        "security": "Security",
        "features": "Features",
        "improvements": "Improvements",
        "fixes": "Bug Fixes",
        "performance": "Performance",
        "deprecations": "Deprecations",
        "infrastructure": "Infrastructure",
        "docs": "Documentation",
        "other": "Other Changes",
    },
    "es": {
        "breaking": "Cambios Importantes",
        "security": "Seguridad",
        "features": "Novedades",
        "improvements": "Mejoras",
        "fixes": "Correcciones",
        "performance": "Rendimiento",
        "deprecations": "Obsolescencias",
        "infrastructure": "Infraestructura",
        "docs": "Documentación",
        "other": "Otros Cambios",
    },
    "ja": {
        "breaking": "破壊的変更",
        "security": "セキュリティ",
        "features": "新機能",
        "improvements": "改善",
        "fixes": "バグ修正",
        "performance": "パフォーマンス",
        "deprecations": "非推奨",
        "infrastructure": "インフラ",
        "docs": "ドキュメント",
        "other": "その他",
    },
    "zh": {
        "breaking": "重大变更",
        "security": "安全",
        "features": "新功能",
        "improvements": "改进",
        "fixes": "错误修复",
        "performance": "性能",
        "deprecations": "废弃",
        "infrastructure": "基础设施",
        "docs": "文档",
        "other": "其他变更",
    },
    "pt": {
        "breaking": "Mudanças Importantes",
        "security": "Segurança",
        "features": "Novidades",
        "improvements": "Melhorias",
        "fixes": "Correções",
        "performance": "Desempenho",
        "deprecations": "Depreciações",
        "infrastructure": "Infraestrutura",
        "docs": "Documentação",
        "other": "Outras Mudanças",
    },
    "de": {
        "breaking": "Wichtige Änderungen",
        "security": "Sicherheit",
        "features": "Neue Funktionen",
        "improvements": "Verbesserungen",
        "fixes": "Fehlerbehebungen",
        "performance": "Leistung",
        "deprecations": "Veraltete Funktionen",
        "infrastructure": "Infrastruktur",
        "docs": "Dokumentation",
        "other": "Sonstige Änderungen",
    },
    "fr": {
        "breaking": "Changements Majeurs",
        "security": "Sécurité",
        "features": "Nouvelles Fonctionnalités",
        "improvements": "Améliorations",
        "fixes": "Corrections de Bugs",
        "performance": "Performance",
        "deprecations": "Dépréciations",
        "infrastructure": "Infrastructure",
        "docs": "Documentation",
        "other": "Autres Changements",
    },
}

# Tone descriptions for LLM prompts
TONE_DESCRIPTIONS: dict[str, str] = {
    "formal": "Use formal, professional language appropriate for official documentation.",
    "casual": "Use casual, conversational language that's friendly and approachable.",
    "professional": "Use clear, professional language that's informative but not stiff.",
    "excited": ("Use enthusiastic, energetic language that highlights the excitement of new features!"),
    "friendly": "Use warm, friendly language that makes users feel welcomed and supported.",
}

# Language names for prompt instructions
LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "ja": "Japanese",
    "zh": "Chinese",
    "pt": "Portuguese",
    "de": "German",
    "fr": "French",
    "ko": "Korean",
    "it": "Italian",
    "ru": "Russian",
    "nl": "Dutch",
    "pl": "Polish",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "cs": "Czech",
    "uk": "Ukrainian",
    "el": "Greek",
    "he": "Hebrew",
    "ro": "Romanian",
    "hu": "Hungarian",
    "bg": "Bulgarian",
}


def get_section_name(section: str, language: str, use_emoji: bool = False) -> str:
    """Get the localized section name with optional emoji prefix.

    Args:
        section: The section identifier (e.g., 'breaking', 'features', 'fixes')
        language: The target language code (e.g., 'en', 'es', 'ja')
        use_emoji: Whether to include an emoji prefix

    Returns:
        The localized section name, optionally prefixed with an emoji.
        Falls back to English if the language is not pre-defined,
        or to a capitalized version of the section ID if section is unknown.
    """
    # Get section names for the language, falling back to English
    language_sections = SECTION_NAMES.get(language, SECTION_NAMES.get("en", {}))

    # Get the section name, falling back to a capitalized version of the section ID
    section_name = language_sections.get(section, section.replace("_", " ").title())

    if use_emoji:
        emoji = SECTION_ICONS.get(section, "")
        if emoji:
            return f"{emoji} {section_name}"

    return section_name


def get_tone_description(tone: str) -> str:
    """Get the tone description for LLM prompt guidance.

    Args:
        tone: The tone identifier (e.g., 'formal', 'casual', 'professional')

    Returns:
        The description of how to write in that tone.

    Raises:
        KeyError: If the tone is not recognized.
    """
    if tone not in TONE_DESCRIPTIONS:
        raise KeyError(f"Unknown tone '{tone}'. Valid tones: {list(TONE_DESCRIPTIONS.keys())}")
    return TONE_DESCRIPTIONS[tone]


def get_language_instruction(language: str) -> str:
    """Get the LLM prompt instruction for generating content in a specific language.

    Args:
        language: The target language code (e.g., 'en', 'es', 'ja')

    Returns:
        A prompt instruction telling the LLM to generate content in that language.
    """
    language_name = LANGUAGE_NAMES.get(language, language.upper())

    if language == "en":
        return "Generate all content in English."

    return (
        f"Generate all content in {language_name}. "
        f"Ensure all text, descriptions, and explanations are written in {language_name}, "
        f"not in English. Technical terms may remain in their original form if commonly used."
    )


def get_section_icon(section: str) -> str:
    """Get the emoji icon for a section.

    Args:
        section: The section identifier

    Returns:
        The emoji for the section, or an empty string if not found.
    """
    return SECTION_ICONS.get(section, "")


def is_language_supported(language: str) -> bool:
    """Check if a language has pre-defined section translations.

    Args:
        language: The language code to check

    Returns:
        True if the language has pre-defined translations.
    """
    return language in SECTION_NAMES


def get_supported_languages() -> list:
    """Get the list of languages with pre-defined section translations.

    Returns:
        List of language codes with pre-defined translations.
    """
    return list(SECTION_NAMES.keys())
