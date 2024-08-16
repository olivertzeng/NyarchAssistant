import importlib, subprocess
import re
import os

class ReplaceHelper:
    DISTRO = None

    @staticmethod
    def get_distribution() -> str:
        """
        Get the distribution

        Returns:
            str: distribution name
            
        """
        if ReplaceHelper.DISTRO is None:
            try:
                ReplaceHelper.DISTRO = subprocess.check_output(['flatpak-spawn', '--host', 'bash', '-c', 'lsb_release -ds']).decode('utf-8').strip()
            except subprocess.CalledProcessError:
                ReplaceHelper.DISTRO = "Unknown"
        
        return ReplaceHelper.DISTRO
    
    @staticmethod
    def get_desktop_environment() -> str:
        desktop = os.getenv("XDG_CURRENT_DESKTOP")
        if desktop is None:
            desktop = "Unknown"
        return desktop

def replace_variables(text: str) -> str:
    """
    Replace variables in prompts
    Supported variables:
        {DIR}: current directory
        {DISTRO}: distribution name
        {DE}: desktop environment

    Args:
        text: text of the prompt

    Returns:
        str: text with replaced variables
    """
    text = text.replace("{DIR}", os.getcwd())
    if "{DISTRO}" in text:
        text = text.replace("{DISTRO}", ReplaceHelper.get_distribution())
    if "{DE}" in text:
        text = text.replace("{DE}", ReplaceHelper.get_desktop_environment())
    return text


def markwon_to_pango(markwon_text):
    # Convert headers
    markwon_text = re.sub(r'^(#+) (.*)$', lambda match: f'<span font_weight="bold" font_size="{14 - len(match.group(1)) * 2}">{match.group(2)}</span>', markwon_text, flags=re.MULTILINE)
    
    # Convert bold text
    markwon_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', markwon_text)
    
    # Convert italic text
    markwon_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', markwon_text)
    
    # Convert strikethrough text
    markwon_text = re.sub(r'~(.*?)~', r'<span strikethrough="true">\1</span>', markwon_text)
    
    # Convert links
    markwon_text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', markwon_text)
    
    return markwon_text

def human_readable_size(size: float, decimal_places:int =2) -> str:
    size = int(size)
    unit = ''
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']:
        if size < 1024.0 or unit == 'PiB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def find_module(full_module_name):
    """
    Returns module object if module `full_module_name` can be imported.

    Returns None if module does not exist.

    Exception is raised if (existing) module raises exception during its import.
    """
    if full_module_name == "git+https://github.com/openai/whisper.git":
        full_module_name = "whisper"
    try:
        return importlib.import_module(full_module_name)
    except ImportError as exc:
        if not (full_module_name + '.').startswith(exc.name + '.'):
            raise


def install_module(module, path):
    r = subprocess.check_output(["pip3", "install", "--target", path, module]).decode("utf-8")
    return r

def can_escape_sandbox():
    try:
        r = subprocess.check_output(["flatpak-spawn", "--host", "echo", "test"])
    except subprocess.CalledProcessError as e:
        return False
    return True

def override_prompts(override_setting, PROMPTS):
    prompt_list = {}
    for prompt in PROMPTS:
        if prompt in override_setting:
            prompt_list[prompt] = override_setting[prompt]
        else:
            prompt_list[prompt] = PROMPTS[prompt]
    return prompt_list
