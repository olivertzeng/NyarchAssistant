from typing import Any
import re 
import threading 
import os 
import json 
import time 
import ctypes
from subprocess import Popen 

from gi.repository import Gtk, Adw, Gio, GLib

from ..handlers import Handler

from ..handlers.stt import STTHandler
from ..handlers.tts import TTSHandler
from ..constants import AVAILABLE_EMBEDDINGS, AVAILABLE_LLMS, AVAILABLE_MEMORIES, AVAILABLE_PROMPTS, AVAILABLE_TTS, AVAILABLE_STT, PROMPTS, AVAILABLE_RAGS
from ..handlers.llm import LLMHandler
from ..constants import AVAILABLE_AVATARS, AVAILABLE_TRANSLATORS, AVAILABLE_SMART_PROMPTS

# Nyarch specific 
from ..handlers.avatar import AvatarHandler
from ..handlers.smart_prompt import SmartPromptHandler
from ..handlers.translator import TranslatorHandler

from ..handlers.embeddings import EmbeddingHandler
from ..handlers.memory import MemoryHandler
from ..handlers.rag import RAGHandler

from .widgets import ComboRowHelper, CopyBox 
from .widgets import MultilineEntry
from ..utility import override_prompts
from ..utility.system import can_escape_sandbox, get_spawn_command, open_website, open_folder 

from ..extensions import ExtensionLoader, NewelleExtension

class Settings(Adw.PreferencesWindow):
    def __init__(self,app,headless=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sandbox = can_escape_sandbox()
        self.settings = Gio.Settings.new('moe.nyarchlinux.assistant')
        if not headless:
            self.set_transient_for(app.win)
        self.set_modal(True)
        self.downloading = {}
        self.model_threads = {}
        self.slider_labels = {}
        self.directory = GLib.get_user_config_dir()
        self.extension_path = os.path.join(self.directory, "extensions")
        self.pip_directory = os.path.join(self.directory, "pip")
        self.extensions_cache = os.path.join(self.directory, "extensions_cache")
        # Load extensions 
        self.extensionloader = ExtensionLoader(self.extension_path, pip_path=self.pip_directory,extension_cache=self.extensions_cache, settings=self.settings)
        self.extensionloader.load_extensions()
        self.extensionloader.add_handlers(AVAILABLE_LLMS, AVAILABLE_TTS, AVAILABLE_STT, AVAILABLE_MEMORIES, AVAILABLE_EMBEDDINGS, AVAILABLE_RAGS, AVAILABLE_AVATARS, AVAILABLE_TRANSLATORS, AVAILABLE_SMART_PROMPTS)
        self.extensionloader.add_prompts(PROMPTS, AVAILABLE_PROMPTS)

        # Load custom prompts
        self.custom_prompts = json.loads(self.settings.get_string("custom-prompts"))
        self.prompts_settings = json.loads(self.settings.get_string("prompts-settings"))
        self.prompts = override_prompts(self.custom_prompts, PROMPTS)
        self.sandbox = can_escape_sandbox()
        
        self.cache_handlers()
        self.update_handler_choice()
        # Page building
        self.general_page = Adw.PreferencesPage()
       
        
        # Dictionary containing all the rows for settings update
        self.settingsrows = {}
        # Build the LLMs settings
        self.LLM = Adw.PreferencesGroup(title=_('Language Model'))
        # Add Help Button 
        help = Gtk.Button(css_classes=["flat"], icon_name="info-outline-symbolic")
        help.connect("clicked", lambda button : Popen(get_spawn_command() + ["xdg-open", "https://github.com/qwersyk/Newelle/wiki/User-guide-to-the-available-LLMs"]))
        self.LLM.set_header_suffix(help)
        
        # Add LLMs
        self.general_page.add(self.LLM)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("language-model")
        others_row = Adw.ExpanderRow(title=_('Other LLMs'), subtitle=_("Other available LLM providers"))
        for model_key in AVAILABLE_LLMS: 
           # Time enlapse calculation
           row = self.build_row(AVAILABLE_LLMS, model_key, selected, group)
           if "secondary" in AVAILABLE_LLMS[model_key] and AVAILABLE_LLMS[model_key]["secondary"]:
               others_row.add_row(row)
           else:
                self.LLM.add(row)
        self.LLM.add(others_row)

        # Secondary LLM
        self.SECONDARY_LLM = Adw.PreferencesGroup(title=_('Advanced LLM Settings'))
        # Create row
        secondary_LLM_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("secondary-llm-on", secondary_LLM_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        secondary_LLM = Adw.ExpanderRow(title=_('Secondary Language Model'), subtitle=_("Model used for secondary tasks, like offer, chat name and memory generation"))
        secondary_LLM.add_action(secondary_LLM_enabled)
        # Add LLMs
        self.general_page.add(self.SECONDARY_LLM)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("secondary-language-model")
        others_row = Adw.ExpanderRow(title=_('Other LLMs'), subtitle=_("Other available LLM providers"))
        for model_key in AVAILABLE_LLMS:
           row = self.build_row(AVAILABLE_LLMS, model_key, selected, group, True)
           if "secondary" in AVAILABLE_LLMS[model_key] and AVAILABLE_LLMS[model_key]["secondary"]:
               others_row.add_row(row)
           else:
               secondary_LLM.add_row(row)
        secondary_LLM.add_row(others_row)
        self.SECONDARY_LLM.add(secondary_LLM)
        
        # Build the Embedding settings
        embedding_row = Adw.ExpanderRow(title=_('Embedding Model'), subtitle=_("Embedding is used to trasform text into vectors. Used by Long Term Memory and RAG. Changing it might require you to re-index documents or reset memory."))
        self.SECONDARY_LLM.add(embedding_row)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("embedding-model")
        for key in AVAILABLE_EMBEDDINGS:
           row = self.build_row(AVAILABLE_EMBEDDINGS, key, selected, group) 
           embedding_row.add_row(row)
        
        # Build the Long Term Memory settings
        memory_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("memory-on", memory_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        tts_program = Adw.ExpanderRow(title=_('Long Term Memory'), subtitle=_("Keep memory of old conversations"))
        tts_program.add_action(memory_enabled)
        self.SECONDARY_LLM.add(tts_program)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("memory-model")
        for key in AVAILABLE_MEMORIES:
           row = self.build_row(AVAILABLE_MEMORIES, key, selected, group) 
           tts_program.add_row(row)
        
        # Build the RAG settings
        self.build_rag_settings()

        # Build the TTS settings
        self.Voicegroup = Adw.PreferencesGroup(title=_('Voice'))
        self.general_page.add(self.Voicegroup)
        tts_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("tts-on", tts_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        tts_program = Adw.ExpanderRow(title=_('Text To Speech Program'), subtitle=_("Choose which text to speech to use"))
        tts_program.add_action(tts_enabled)
        self.Voicegroup.add(tts_program)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("tts")
        for tts_key in AVAILABLE_TTS:
           row = self.build_row(AVAILABLE_TTS, tts_key, selected, group) 
           tts_program.add_row(row)
        # Build the Translators settings
        group = Gtk.CheckButton()
        selected = self.settings.get_string("translator")
        tts_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("translator-on", tts_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        translator_program = Adw.ExpanderRow(title=_('Translator program'), subtitle=_("Translate the output of the LLM before passing it to the TTS Program"))
        translator_program.add_action(tts_enabled)
        for translator_key in AVAILABLE_TRANSLATORS:
            row = self.build_row(AVAILABLE_TRANSLATORS, translator_key, selected, group)
            translator_program.add_row(row)
        self.Voicegroup.add(translator_program)
        
        # Build the Speech to Text settings
        stt_engine = Adw.ExpanderRow(title=_('Speech To Text Engine'), subtitle=_("Choose which speech recognition engine you want"))
        self.Voicegroup.add(stt_engine)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("stt-engine")
        for stt_key in AVAILABLE_STT:
            row = self.build_row(AVAILABLE_STT, stt_key, selected, group)
            stt_engine.add_row(row)
        # Automatic STT settings 
        self.auto_stt = Adw.ExpanderRow(title=_('Automatic Speech To Text'), subtitle=_("Automatically restart speech to text at the end of a text/TTS"))
        self.build_auto_stt()
        self.Voicegroup.add(self.auto_stt)
        
        # Build the AVATAR settings
        self.avatargroup = Adw.PreferencesGroup(title=_('Avatar'))
        self.general_page.add(self.avatargroup)
        avatar_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("avatar-on", avatar_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        avatar = Adw.ExpanderRow(title=_('Avatar model'), subtitle=_("Choose which avatar model to choose"))
        avatar.add_action(avatar_enabled)
        self.avatargroup.add(avatar)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("avatar-model")
        for avatar_key in AVAILABLE_AVATARS:
           row = self.build_row(AVAILABLE_AVATARS, avatar_key, selected, group) 
           avatar.add_row(row) 
        # Build the Smart Prompt settings
        self.smartpromptgroup = Adw.PreferencesGroup(title=_('Smart Prompt'))
        self.general_page.add(self.smartpromptgroup)
        smart_prompt_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("smart-prompt-on", smart_prompt_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        smartprompt = Adw.ExpanderRow(title=_('Smart Prompt selector'), subtitle=_("Choose which smart prompt model to choose"))
        smartprompt.add_action(smart_prompt_enabled)
        self.smartpromptgroup.add(smartprompt)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("smart-prompt")
        for smart_prompt_key in AVAILABLE_SMART_PROMPTS:
           row = self.build_row(AVAILABLE_SMART_PROMPTS, smart_prompt_key, selected, group) 
           smartprompt.add_row(row)
        
        # Prompts settings
        self.prompt = Adw.PreferencesGroup(title=_('Prompt control'))
        self.general_page.add(self.prompt)

        row = Adw.ActionRow(title=_("Auto-run commands"), subtitle=_("Commands that the bot will write will automatically run"))
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        row.add_suffix(switch)
        self.settings.bind("auto-run", switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.prompt.add(row)

        self.__prompts_entries = {}
        for prompt in AVAILABLE_PROMPTS:
            is_active = False
            if prompt["setting_name"] in self.prompts_settings:
                is_active = self.prompts_settings[prompt["setting_name"]]
            else:
                is_active = prompt["default"]
            if not prompt["show_in_settings"]:
                continue
            row = Adw.ExpanderRow(title=prompt["title"], subtitle=prompt["description"])
            if prompt["editable"]:
                self.add_customize_prompt_content(row, prompt["key"])
            switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            switch.set_active(is_active)
            switch.connect("notify::active", self.update_prompt, prompt["setting_name"])
            row.add_suffix(switch)
            self.prompt.add(row)

        # Interface settings
        self.interface = Adw.PreferencesGroup(title=_('Interface'))
        self.general_page.add(self.interface)

        row = Adw.ActionRow(title=_("Hidden files"), subtitle=_("Show hidden files"))
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        row.add_suffix(switch)
        self.settings.bind("hidden-files", switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.interface.add(row)

        row = Adw.ActionRow(title=_("Display LaTex"), subtitle=_("Display LaTex formulas in chat"))
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        row.add_suffix(switch)
        self.settings.bind("display-latex", switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.interface.add(row)

        row = Adw.ActionRow(title=_("Reverse Chat Order"), subtitle=_("Show most recent chats on top in chat list (change chat to apply)"))
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        row.add_suffix(switch)
        self.settings.bind("reverse-order", switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.interface.add(row)
        
        row = Adw.ActionRow(title=_("Automatically Generate Chat Names"), subtitle=_("Generate chat names automatically after the first two messages"))
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        row.add_suffix(switch)
        self.settings.bind("auto-generate-name", switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.interface.add(row)
        
        row = Adw.ActionRow(title=_("Number of offers"), subtitle=_("Number of message suggestions to send to chat "))
        int_spin = Gtk.SpinButton(valign=Gtk.Align.CENTER)
        int_spin.set_adjustment(Gtk.Adjustment(lower=0, upper=5, step_increment=1, page_increment=10, page_size=0))
        row.add_suffix(int_spin)
        self.settings.bind("offers", int_spin, 'value', Gio.SettingsBindFlags.DEFAULT)
        self.interface.add(row)
        
        # Neural Network Control
        self.neural_network = Adw.PreferencesGroup(title=_('Neural Network Control'))
        self.general_page.add(self.neural_network) 

        row = Adw.ActionRow(title=_("Command virtualization"), subtitle=_("Run commands in a virtual machine"))
        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        row.add_suffix(switch)
        # Set default value for the switch
        if not self.sandbox:
            switch.set_active(True)
            self.settings.set_boolean("virtualization", True)
        else:
            switch.set_active(self.settings.get_boolean("virtualization"))
        # Connect the function
        switch.connect("state-set", self.toggle_virtualization)
        self.neural_network.add(row)
        
        row = Adw.ExpanderRow(title=_("External Terminal"), subtitle=_("Choose the external terminal where to run the console commands"))
        entry = Gtk.Entry()
        self.settings.bind("external-terminal", entry, 'text', Gio.SettingsBindFlags.DEFAULT)
        row.add_row(entry)
        self.neural_network.add(row)
        # Set default value for the switch        
        row = Adw.ActionRow(title=_("Program memory"), subtitle=_("How long the program remembers the chat "))
        int_spin = Gtk.SpinButton(valign=Gtk.Align.CENTER)
        int_spin.set_adjustment(Gtk.Adjustment(lower=0, upper=30, step_increment=1, page_increment=10, page_size=0))
        row.add_suffix(int_spin)
        self.settings.bind("memory", int_spin, 'value', Gio.SettingsBindFlags.DEFAULT)
        self.neural_network.add(row)

        self.add(self.general_page)

    def build_rag_settings(self):
        self.RAG = Adw.PreferencesGroup(title=_('Document Sources (RAG)'), description=_("Include content from your documents in the responses"))
        tts_program = Adw.ExpanderRow(title=_('Document Analyzer'), subtitle=_("The document analyzer uses multiple techniques to extract relevant information about your documents"))
        #tts_program.add_action(memory_enabled)
        self.RAG.add(tts_program)
        group = Gtk.CheckButton()
        selected = self.settings.get_string("rag-model")
        for key in AVAILABLE_RAGS:
           row = self.build_row(AVAILABLE_RAGS, key, selected, group) 
           tts_program.add_row(row)
       
        rag_on_docuements = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("rag-on-documents", rag_on_docuements, 'active', Gio.SettingsBindFlags.DEFAULT)
        rag_row = Adw.ActionRow(title=_("Read documents if unsupported"), subtitle=_("If the LLM does not support reading documents, relevant information about documents sent in the chat will be given to the LLM using your Document Analyzer."))
        rag_row.add_suffix(rag_on_docuements)
        self.RAG.add(rag_row)
        # Document folder 
        rag_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("rag-on", rag_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        document_folder = Adw.ExpanderRow(title=_("Document Folder"), subtitle=_("Put the documents you want to query in your document folder. The document analyzer will find relevant information in them if this option is enabled"))
        document_folder.add_suffix(rag_enabled)
        # Document folder rows 
        folder = Adw.ActionRow(title="Open your document folder", subtitle=_("Put all the documents you want to index in this folder"))
        folder_button = Gtk.Button(icon_name="folder-symbolic", css_classes=["flat"])
        folder_button.connect("clicked", lambda _: open_folder(os.path.join(self.directory, "documents")))
        folder.add_suffix(folder_button)
        document_folder.add_row(folder)
        
        self.rag_handler = self.get_object(AVAILABLE_RAGS, selected) 
        self.rag_index = self.create_extra_setting(self.rag_handler.get_index_row(), self.rag_handler, AVAILABLE_RAGS) 
        document_folder.add_row(self.rag_index)
        self.document_folder = document_folder

        self.RAG.add(document_folder)
        self.general_page.add(self.RAG)
    
    def update_rag_index(self):
        self.rag_handler = self.get_object(AVAILABLE_RAGS, self.settings.get_string("rag-model"))
        self.document_folder.remove(self.rag_index)
        self.rag_index = self.create_extra_setting(self.rag_handler.get_index_row(), self.rag_handler, AVAILABLE_RAGS)
        self.document_folder.add_row(self.rag_index)

    def build_auto_stt(self):
        auto_stt_enabled = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.settings.bind("automatic-stt", auto_stt_enabled, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.auto_stt.add_suffix(auto_stt_enabled) 
        def update_scale(scale, label, setting_value, type):
            value = scale.get_value()
            if type is float:
                self.settings.set_double(setting_value, value)
            elif type is int:
                value = int(value)
                self.settings.set_int(setting_value, value)
            label.set_text(str(value))

        # Silence Threshold
        silence_threshold = Adw.ActionRow(title=_("Silence threshold"), subtitle=_("Silence threshold in seconds, percentage of the volume to be considered silence"))
        threshold = Gtk.Scale(digits=0, round_digits=2)
        threshold.set_range(0, 0.5)
        threshold.set_size_request(120, -1)
        th = self.settings.get_double("stt-silence-detection-threshold")
        label = Gtk.Label(label=str(th))
        threshold.set_value(th)
        threshold.connect("value-changed", update_scale, label, "stt-silence-detection-threshold", float)
        box = Gtk.Box()
        box.append(threshold)
        box.append(label)
        silence_threshold.add_suffix(box)
        # Silence time 
        silence_time = Adw.ActionRow(title=_("Silence time"), subtitle=_("Silence time in seconds before recording stops automatically"))
        time_scale = Gtk.Scale(digits=0, round_digits=0)
        time_scale.set_range(0, 10)
        time_scale.set_size_request(120, -1)
        value = self.settings.get_int("stt-silence-detection-duration")
        time_scale.set_value(value)
        label = Gtk.Label(label=str(value))
        time_scale.connect("value-changed", update_scale, label, "stt-silence-detection-duration", int)
        box = Gtk.Box()
        box.append(time_scale)
        box.append(label)
        silence_time.add_suffix(box)
        self.auto_stt.add_row(silence_threshold) 
        self.auto_stt.add_row(silence_time) 

    def update_prompt(self, switch: Gtk.Switch, state, key: str):
        """Update the prompt in the settings

        Args:
            switch: the switch widget
            key: the key of the prompt
        """
        self.prompts_settings[key] = switch.get_active()
        self.settings.set_string("prompts-settings", json.dumps(self.prompts_settings))

    def build_row(self, constants: dict[str, Any], key: str, selected: str, group: Gtk.CheckButton, secondary: bool = False) -> Adw.ActionRow | Adw.ExpanderRow:
        """Build the row for every handler

        Args:
            constants: The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            key: key of the specified handler
            selected: the key of the selected handler
            group: the check group for che checkbox in the row
            secondary: if to use secondary settings

        Returns:
            The created row
        """
        model = constants[key]
        handler = self.get_object(constants, key, secondary)
        # Check if the model is the currently selected
        active = False
        if model["key"] == selected:
            active = True
        # Define the type of row
        self.settingsrows[(key, self.convert_constants(constants), secondary)] = {}
        if len(handler.get_extra_settings()) > 0:
             row = Adw.ExpanderRow(title=model["title"], subtitle=model["description"])
             self.add_extra_settings(constants, handler, row)
        else:
            row = Adw.ActionRow(title=model["title"], subtitle=model["description"])
        self.settingsrows[(key, self.convert_constants(constants), secondary)]["row"] = row
        
        # Add extra buttons 
        threading.Thread(target=self.add_download_button, args=(handler, row)).start()
        self.add_flatpak_waning_button(handler, row)
       
        # Add copy settings button if it's secondary 
        if secondary:
            button = Gtk.Button(css_classes=["flat"], icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER)
            button.connect("clicked", self.copy_settings, constants, handler)
            row.add_suffix(button)
        if "website" in model:
            row.add_suffix(self.create_web_button(model["website"]))
        # Add check button
        button = Gtk.CheckButton(name=key, group=group, active=active)
        button.connect("toggled", self.choose_row, constants, secondary)
        self.settingsrows[(key, self.convert_constants(constants), secondary)]["button"] = button 
        if not self.sandbox and handler.requires_sandbox_escape() or not handler.is_installed():
            button.set_sensitive(False)
        row.add_prefix(button)

        return row

    def copy_settings(self, button, constants: dict[str, Any], handler: Handler):
        """Copy the settings"""
        primary = self.get_object(constants, handler.key, False)
        secondary = self.get_object(constants, handler.key, True)
        for setting in primary.get_all_settings():
            secondary.set_setting(setting, primary.get_setting(setting))
        self.on_setting_change(constants, handler, "", True)


    def update_handler_choice(self):
        """Update handlers for Memory and RAG"""
        self.language_model = self.settings.get_string("language-model")
        self.secondary_language_model = self.settings.get_string("secondary-language-model")
        self.use_secondary_language_model = self.settings.get_boolean("secondary-llm-on")
        self.embedding_model = self.settings.get_string("embedding-model")
        if self.use_secondary_language_model and self.secondary_language_model in AVAILABLE_LLMS:
            llm = self.get_object(AVAILABLE_LLMS, self.secondary_language_model, True)
        elif not self.use_secondary_language_model and self.language_model in AVAILABLE_LLMS:
            llm = self.get_object(AVAILABLE_LLMS, self.language_model)
        else:
            llm = None
        embedding = self.get_object(AVAILABLE_EMBEDDINGS, self.embedding_model)
        for key in AVAILABLE_MEMORIES:
            self.get_object(AVAILABLE_MEMORIES, key).set_handlers(llm, embedding)
        for key in AVAILABLE_RAGS:
            self.get_object(AVAILABLE_RAGS, key).set_handlers(llm, embedding)

    def cache_handlers(self):
        self.handlers = {}
        for key in AVAILABLE_TTS:
            self.handlers[(key, self.convert_constants(AVAILABLE_TTS))] = self.get_object(AVAILABLE_TTS, key)
        for key in AVAILABLE_STT:
            self.handlers[(key, self.convert_constants(AVAILABLE_STT))] = self.get_object(AVAILABLE_STT, key)
        for key in AVAILABLE_LLMS:
            self.handlers[(key, self.convert_constants(AVAILABLE_LLMS), False)] = self.get_object(AVAILABLE_LLMS, key)
        # Secondary LLMs
        for key in AVAILABLE_LLMS:
            self.handlers[(key, self.convert_constants(AVAILABLE_LLMS), True)] = self.get_object(AVAILABLE_LLMS, key, True)
        for key in AVAILABLE_MEMORIES:
            self.handlers[(key, self.convert_constants(AVAILABLE_MEMORIES), False)] = self.get_object(AVAILABLE_MEMORIES, key)
        for key in AVAILABLE_RAGS:
            self.handlers[(key, self.convert_constants(AVAILABLE_RAGS), False)] = self.get_object(AVAILABLE_RAGS, key)
        
        # Nyarch Hanlders
        for key in AVAILABLE_AVATARS:
            self.handlers[(key, self.convert_constants(AVAILABLE_AVATARS))] = self.get_object(AVAILABLE_AVATARS, key)
        for key in AVAILABLE_TRANSLATORS:
            self.handlers[(key, self.convert_constants(AVAILABLE_TRANSLATORS))] = self.get_object(AVAILABLE_TRANSLATORS, key)
        for key in AVAILABLE_SMART_PROMPTS:
            self.handlers[(key, self.convert_constants(AVAILABLE_SMART_PROMPTS))] = self.get_object(AVAILABLE_SMART_PROMPTS, key)
    
    def get_object(self, constants: dict[str, Any], key:str, secondary=False) -> (Handler):
        """Get an handler instance for the specified handler key

        Args:
            constants: The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            key: key of the specified handler
            secondary: if to use secondary settings

        Raises:
            Exception: if the constant is not valid 

        Returns:
            The created handler           
        """
        if (key, self.convert_constants(constants), secondary) in self.handlers:
            return self.handlers[(key, self.convert_constants(constants), secondary)]

        if constants == AVAILABLE_LLMS:
            model = constants[key]["class"](self.settings, os.path.join(self.directory, "models"))
            model.set_secondary_settings(secondary)
        elif constants == AVAILABLE_STT:
            model = constants[key]["class"](self.settings,os.path.join(self.directory, "models"))
        elif constants == AVAILABLE_TTS:
            model = constants[key]["class"](self.settings, os.path.join(self.directory, "models"))
        elif constants == AVAILABLE_MEMORIES:
            model = constants[key]["class"](self.settings, os.path.join(self.directory, "models"))
        elif constants == AVAILABLE_EMBEDDINGS:
            model = constants[key]["class"](self.settings, os.path.join(self.directory, "models"))
        elif constants == AVAILABLE_RAGS:
            model = constants[key]["class"](self.settings, os.path.join(self.directory, "models"))
        elif constants == AVAILABLE_AVATARS:
            model = constants[key]["class"](self.settings, self.directory)
        elif constants == AVAILABLE_TRANSLATORS:
            model = constants[key]["class"](self.settings, self.directory)
        elif constants == AVAILABLE_SMART_PROMPTS:
            model = constants[key]["class"](self.settings, self.directory)
        elif constants == self.extensionloader.extensionsmap:
            model = self.extensionloader.extensionsmap[key]
            if model is None:
                raise Exception("Extension not found")
        else:
            raise Exception("Unknown constants")
        return model
    
    def convert_constants(self, constants: str | dict[str, Any]) -> (str | dict):
        """Get an handler instance for the specified handler key

        Args:
            constants: The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            key: key of the specified handler

        Raises:
            Exception: if the constant is not valid 

        Returns:
            The created handler           
        """
        if type(constants) is str:
            match constants:
                case "tts":
                    return AVAILABLE_TTS
                case "stt":
                    return AVAILABLE_STT
                case "llm":
                    return AVAILABLE_LLMS
                case "memory":
                    return AVAILABLE_MEMORIES
                case "embedding":
                    return AVAILABLE_EMBEDDINGS
                case "rag":
                    return AVAILABLE_RAGS
                case "avatar":
                    return AVAILABLE_AVATARS
                case "translator":
                    return AVAILABLE_TRANSLATORS
                case "smart-prompt":
                    return AVAILABLE_SMART_PROMPTS
                case "extension":
                    return self.extensionloader.extensionsmap
                case _:
                    raise Exception("Unknown constants")
        else:
            if constants == AVAILABLE_LLMS:
                return "llm"
            elif constants == AVAILABLE_STT:
                return "stt"
            elif constants == AVAILABLE_TTS:
                return "tts"
            elif constants == AVAILABLE_MEMORIES:
                return "memory"
            elif constants == AVAILABLE_EMBEDDINGS:
                return "embedding"
            elif constants == AVAILABLE_RAGS:
                return "rag"
            elif constants == AVAILABLE_AVATARS:
                return "avatar"
            elif constants == AVAILABLE_TRANSLATORS:
                return "translator"
            elif constants == AVAILABLE_SMART_PROMPTS:
                return "smart-prompt"
            elif constants == self.extensionloader.extensionsmap:
                return "extension"
            else:
                raise Exception("Unknown constants")

    def get_constants_from_object(self, handler: Handler) -> dict[str, Any]:
        """Get the constants from an hander

        Args:
            handler: the handler 

        Raises:
            Exception: if the handler is not known

        Returns: AVAILABLE_LLMS, AVAILABLE_STT, AVAILABLE_TTS based on the type of the handler 
        """
        if issubclass(type(handler), TTSHandler):
            return AVAILABLE_TTS
        elif issubclass(type(handler), STTHandler):
            return AVAILABLE_STT
        elif issubclass(type(handler), LLMHandler):
            return AVAILABLE_LLMS
        elif issubclass(type(handler), AvatarHandler):
            return AVAILABLE_AVATARS
        elif issubclass(type(handler), TranslatorHandler):
            return AVAILABLE_TRANSLATORS
        elif issubclass(type(handler), SmartPromptHandler):
            return AVAILABLE_SMART_PROMPTS
        elif issubclass(type(handler), NewelleExtension):
            return self.extensionloader.extensionsmap
        elif issubclass(type(handler), MemoryHandler):
            return AVAILABLE_MEMORIES
        elif issubclass(type(handler), EmbeddingHandler):
            return AVAILABLE_EMBEDDINGS
        elif issubclass(type(handler), RAGHandler):
            return AVAILABLE_RAGS
        else:
            raise Exception("Unknown handler")

    def choose_row(self, button, constants : dict, secondary=False):
        """Called by GTK the selected h
        andler is changed

        Args:
            button (): the button that triggered the change
            constants: The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
        """
        setting_name = ""
        if constants == AVAILABLE_LLMS:
            if secondary:
                setting_name = "secondary-language-model"
            else:
                setting_name = "language-model"
        elif constants == AVAILABLE_TTS:
            setting_name = "tts"
        elif constants == AVAILABLE_STT:
            setting_name = "stt-engine"
        elif constants == AVAILABLE_MEMORIES:
            setting_name = "memory-model"
        elif constants == AVAILABLE_EMBEDDINGS:
            setting_name = "embedding-model"
        elif constants == AVAILABLE_RAGS:
            setting_name = "rag-model"
        elif constants == AVAILABLE_AVATARS:
            setting_name = "avatar-model"
        elif constants == AVAILABLE_TRANSLATORS:
            setting_name = "translator"
        elif constants == AVAILABLE_SMART_PROMPTS:
            setting_name = "smart-prompt"
        else:
            return
        self.settings.set_string(setting_name, button.get_name())
        self.update_handler_choice()
        if constants == AVAILABLE_RAGS:
            self.update_rag_index()

    def add_extra_settings(self, constants : dict[str, Any], handler : Handler, row : Adw.ExpanderRow, nested_settings : list | None = None):
        """Buld the extra settings for the specified handler. The extra settings are specified by the method get_extra_settings 
            Extra settings format:
            Required parameters:
            - title: small title for the setting 
            - description: description for the setting
            - default: default value for the setting
            - type: What type of row to create, possible rows:
                - entry: input text 
                - toggle: bool
                - combo: for multiple choice
                    - values: list of touples of possible values (display_value, actual_value)
                - range: for number input with a slider 
                    - min: minimum value
                    - max: maximum value 
                    - round: how many digits to round 
            Optional parameters:
                - folder: add a button that opens a folder with the specified path
                - website: add a button that opens a website with the specified path
                - update_settings (bool) if reload the settings in the settings page for the specified handler after that setting change
        Args:
            constants: The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            handler: An instance of the handler
            row: row where to add the settings
        """
        if nested_settings is None:
            self.settingsrows[(handler.key, self.convert_constants(constants), handler.is_secondary())]["extra_settings"] = []
            settings = handler.get_extra_settings()
        else:
            settings = nested_settings
        for setting in settings:
            r = self.create_extra_setting(setting, handler, constants) 
            row.add_row(r)
            self.settingsrows[handler.key, self.convert_constants(constants), handler.is_secondary()]["extra_settings"].append(r)
        handler.set_extra_settings_update(lambda _: GLib.idle_add(self.on_setting_change, constants, handler, handler.key, True))
    
    def create_extra_setting(self, setting : dict, handler: Handler, constants : dict[str, Any]) -> Adw.ExpanderRow | Adw.ActionRow:
        if setting["type"] == "entry":
            r = Adw.ActionRow(title=setting["title"], subtitle=setting["description"])
            value = handler.get_setting(setting["key"])
            value = str(value)
            entry = Gtk.Entry(valign=Gtk.Align.CENTER, text=value, name=setting["key"])
            entry.connect("changed", self.setting_change_entry, constants, handler)
            r.add_suffix(entry)
        elif setting["type"] == "multilineentry":
            r = Adw.ExpanderRow(title=setting["title"], subtitle=setting["description"])
            value = handler.get_setting(setting["key"])
            value = str(value)
            entry = MultilineEntry()
            entry.set_text(value)
            entry.set_on_change(self.setting_change_multilinentry)
            entry.name = setting["key"]
            entry.constants = constants
            entry.handler = handler
            r.add_row(entry)
        elif setting["type"] == "button":
            r = Adw.ActionRow(title=setting["title"], subtitle=setting["description"])
            button = Gtk.Button(valign=Gtk.Align.CENTER, name=setting["key"])
            if "label" in setting:
                button.set_label(setting["label"])
            elif "icon" in setting:
                button.set_icon_name(setting["icon"])
            button.connect("clicked", setting["callback"])
            r.add_suffix(button)
        elif setting["type"] == "toggle":
            r = Adw.ActionRow(title=setting["title"], subtitle=setting["description"])
            value = handler.get_setting(setting["key"])
            value = bool(value)
            toggle = Gtk.Switch(valign=Gtk.Align.CENTER, active=value, name=setting["key"])
            toggle.connect("state-set", self.setting_change_toggle, constants, handler)
            r.add_suffix(toggle)
        elif setting["type"] == "combo":
            r = Adw.ComboRow(title=setting["title"], subtitle=setting["description"], name=setting["key"])
            helper = ComboRowHelper(r, setting["values"], handler.get_setting(setting["key"]))
            helper.connect("changed", self.setting_change_combo, constants, handler)
        elif setting["type"] == "range":
            r = Adw.ActionRow(title=setting["title"], subtitle=setting["description"], valign=Gtk.Align.CENTER)
            box = Gtk.Box()
            scale = Gtk.Scale(name=setting["key"], round_digits=setting["round-digits"])
            scale.set_range(setting["min"], setting["max"]) 
            scale.set_value(round(handler.get_setting(setting["key"]), setting["round-digits"]))
            scale.set_size_request(120, -1)
            scale.connect("change-value", self.setting_change_scale, constants, handler)
            label = Gtk.Label(label=handler.get_setting(setting["key"]))
            box.append(label)
            box.append(scale)
            self.slider_labels[scale] = label
            r.add_suffix(box)
        elif setting["type"] == "nested":
            r = Adw.ExpanderRow(title=setting["title"], subtitle=setting["description"])
            self.add_extra_settings(constants, handler, r, setting["extra_settings"])
        elif setting["type"] == "download":
            r = Adw.ActionRow(title=setting["title"], subtitle=setting["description"]) 
            
            actionbutton = Gtk.Button(css_classes=["flat"],valign=Gtk.Align.CENTER)
            if setting["is_installed"]:
                actionbutton.set_icon_name("user-trash-symbolic")
                actionbutton.connect("clicked", lambda button,cb=setting["callback"],key=setting["key"] : cb(key))
                actionbutton.add_css_class("error")
            else:
                actionbutton.set_icon_name("folder-download-symbolic" if "download-icon" not in setting else setting["download-icon"])
                actionbutton.connect("clicked", self.download_setting, setting, handler)
                actionbutton.add_css_class("accent")
            r.add_suffix(actionbutton)
        else:
            return
        if "website" in setting:
            wbbutton = self.create_web_button(setting["website"])
            r.add_prefix(wbbutton)
        if "folder" in setting:
            wbbutton = self.create_web_button(setting["folder"], folder=True)
            r.add_suffix(wbbutton)
        if "refresh" in setting:
            refresh_icon = setting.get("refresh_icon", "view-refresh-symbolic")
            refreshbutton = Gtk.Button(icon_name=refresh_icon, valign=Gtk.Align.CENTER, css_classes=["flat"])
            refreshbutton.connect("clicked", setting["refresh"])
            r.add_suffix(refreshbutton)
        return r 
    
    def add_customize_prompt_content(self, row, prompt_name):
        """Add a MultilineEntry to edit a prompt from the given prompt name

        Args:
            row (): row of the prompt 
            prompt_name (): name of the prompt 
        """
        box = Gtk.Box()
        entry = MultilineEntry()
        entry.set_text(self.prompts[prompt_name])
        self.__prompts_entries[prompt_name] = entry
        entry.set_name(prompt_name)
        entry.set_on_change(self.edit_prompt)

        wbbutton = Gtk.Button(icon_name="star-filled-rounded-symbolic")
        wbbutton.add_css_class("flat")
        wbbutton.set_valign(Gtk.Align.CENTER)
        wbbutton.set_name(prompt_name)
        wbbutton.connect("clicked", self.restore_prompt)

        box.append(entry)
        box.append(wbbutton)
        row.add_row(box)

    def edit_prompt(self, entry):
        """Called when the MultilineEntry is changed

        Args:
            entry : the MultilineEntry 
        """
        prompt_name = entry.get_name()
        prompt_text = entry.get_text()

        if prompt_text == PROMPTS[prompt_name]:
            del self.custom_prompts[entry.get_name()]
        else:
            self.custom_prompts[prompt_name] = prompt_text
            self.prompts[prompt_name] = prompt_text
        self.settings.set_string("custom-prompts", json.dumps(self.custom_prompts))

    def restore_prompt(self, button):
        """Called when the prompt restore is called

        Args:
            button (): the clicked button 
        """
        prompt_name = button.get_name()
        self.prompts[prompt_name] = PROMPTS[prompt_name]
        self.__prompts_entries[prompt_name].set_text(self.prompts[prompt_name])



    def toggle_virtualization(self, toggle, status):
        """Called when virtualization is toggled, also checks if there are enough permissions. If there aren't show a warning

        Args:
            toggle (): 
            status (): 
        """
        if not self.sandbox and not status:
            self.show_flatpak_sandbox_notice()            
            toggle.set_active(True)
            self.settings.set_boolean("virtualization", True)
        else:
            self.settings.set_boolean("virtualization", status)

        

    def on_setting_change(self, constants: dict[str, Any], handler: Handler, key: str, force_change : bool = False):

        
        if not force_change:
            setting_info = [info for info in handler.get_extra_settings_list() if info["key"] == key][0]
        else:
            setting_info = {}
        if force_change or "update_settings" in setting_info and setting_info["update_settings"]:
            # remove all the elements in the specified expander row 
            row = self.settingsrows[(handler.key, self.convert_constants(constants), handler.is_secondary())]["row"]
            setting_list = self.settingsrows[(handler.key, self.convert_constants(constants), handler.is_secondary())]["extra_settings"]
            if constants == AVAILABLE_RAGS:
                GLib.idle_add(self.update_rag_index)
            for setting_row in setting_list:
                row.remove(setting_row)
            self.add_extra_settings(constants, handler, row)


    def setting_change_entry(self, entry, constants, handler : Handler):
        """ Called when an entry handler setting is changed 

        Args:
            entry (): the entry whose contents are changed
            constants : The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            handler: An instance of the specified handler
        """
        name = entry.get_name()
        handler.set_setting(name, entry.get_text())
        self.on_setting_change(constants, handler, name)

    def setting_change_multilinentry(self, entry):
        """ Called when an entry handler setting is changed 

        Args:
            entry (): the entry whose contents are changed
            constants : The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            handler: An instance of the specified handler
        """
        entry.handler.set_setting(entry.name, entry.get_text())
        self.on_setting_change(entry.constants, entry.handler, entry.name)

    def setting_change_toggle(self, toggle, state, constants, handler):
        """Called when a toggle for the handler setting is triggered

        Args:
            toggle (): the specified toggle 
            state (): state of the toggle
            constants (): The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            handler (): an instance of the handler
        """
        enabled = toggle.get_active()
        handler.set_setting(toggle.get_name(), enabled)
        self.on_setting_change(constants, handler, toggle.get_name())

    def setting_change_scale(self, scale, scroll, value, constants, handler):
        """Called when a scale for the handler setting is changed

        Args:
            scale (): the changed scale
            scroll (): scroll value
            value (): the value 
            constants (): The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            handler (): an instance of the handler
        """
        setting = scale.get_name()
        digits = scale.get_round_digits()
        value = round(value, digits)
        self.slider_labels[scale].set_label(str(value))
        handler.set_setting(setting, value)
        self.on_setting_change(constants, handler, setting)

    def setting_change_combo(self, helper, value, constants, handler):
        """Called when a combo for the handler setting is changed

        Args:
            helper (): combo row helper 
            value (): chosen value
            constants (): The constants for the specified handler, can be AVAILABLE_TTS, AVAILABLE_STT...
            handler (): an instance of the handler
        """
        setting = helper.combo.get_name()
        handler.set_setting(setting, value)
        self.on_setting_change(constants, handler, setting)


    def add_download_button(self, handler : Handler, row : Adw.ActionRow | Adw.ExpanderRow): 
        """Add download button for an handler dependencies. If clicked it will call handler.install()

        Args:
            handler: an instance of the handler
            row: row where to add teh button
        """
        actionbutton = Gtk.Button(css_classes=["flat"], valign=Gtk.Align.CENTER)
        if not handler.is_installed():
            icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="folder-download-symbolic"))
            actionbutton.connect("clicked", self.install_model, handler)
            actionbutton.add_css_class("accent")
            actionbutton.set_child(icon)
            if type(row) is Adw.ActionRow:
                row.add_suffix(actionbutton)
            elif type(row) is Adw.ExpanderRow:
                row.add_action(actionbutton)

    def add_flatpak_waning_button(self, handler : Handler, row : Adw.ExpanderRow | Adw.ActionRow | Adw.ComboRow):
        """Add flatpak warning button in case the application does not have enough permissions
        On click it will show a warning about this issue and how to solve it

        Args:
            handler: an instance of the handler
            row: the row where to add the button
        """
        actionbutton = Gtk.Button(css_classes=["flat"], valign=Gtk.Align.CENTER)
        if handler.requires_sandbox_escape() and not self.sandbox:
            icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="warning-outline-symbolic"))
            actionbutton.connect("clicked", self.show_flatpak_sandbox_notice)
            actionbutton.add_css_class("error")
            actionbutton.set_child(icon)
            if type(row) is Adw.ActionRow:
                row.add_suffix(actionbutton)
            elif type(row) is Adw.ExpanderRow:
                row.add_action(actionbutton)
            elif type(row) is Adw.ComboRow:
                row.add_suffix(actionbutton)

    def install_model(self, button, handler):
        """Display a spinner and trigger the dependency download on another thread

        Args:
            button (): the specified button
            handler (): handler of the model
        """
        spinner = Gtk.Spinner(spinning=True)
        button.set_child(spinner)
        button.set_sensitive(False)
        t = threading.Thread(target=self.install_model_async, args= (button, handler))
        t.start()

    def install_model_async(self, button, model):
        """Install the model dependencies, called on another thread

        Args:
            button (): button  
            model (): a handler instance
        """
        model.install()
        GLib.idle_add(self.update_ui_after_install, button, model)

    def update_ui_after_install(self, button, model):
        """Update the UI after a model installation

        Args:
            button (): button 
            model (): a handler instance 
        """
        if model.is_installed():
            self.on_setting_change(self.get_constants_from_object(model), model, "", True)
        button.set_child(None)
        button.set_sensitive(False)
        checkbutton = self.settingsrows[(model.key, self.convert_constants(self.get_constants_from_object(model)), model.is_secondary())]["button"]
        checkbutton.set_sensitive(True)

    def download_setting(self, button: Gtk.Button, setting, handler: Handler, uninstall=False):
        """Download the setting for the given handler

        Args:
            button (): button pressed
            setting (): setting to download
            handler (): handler to download the setting for
        """

        if uninstall:
            return
        box = Gtk.Box(homogeneous=True, spacing=4)
        box.set_orientation(Gtk.Orientation.VERTICAL)
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="folder-download-symbolic" if "download-icon" not in setting else setting["download-icon"]))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        progress = Gtk.ProgressBar(hexpand=False)
        progress.set_size_request(4, 4)
        box.append(icon)
        box.append(progress)
        button.set_child(box)
        button.disconnect_by_func(self.download_setting)
        button.connect("clicked", lambda x: setting["callback"](setting["key"]))
        th = threading.Thread(target=self.download_setting_thread, args=(handler, setting, button, progress))
        self.model_threads[(setting["key"]), handler.key] = [th, 0]
        th.start()

    def update_download_status_setting(self, handler, setting, progressbar):
        """Periodically update the progressbar for the download

        Args:
            model (): model that is being downloaded
            filesize (): filesize of the download
            progressbar (): the bar to update
        """
        while (setting["key"], handler.key) in self.downloading and self.downloading[(setting["key"], handler.key)]:
            try:
                perc = setting["download_percentage"](setting["key"])
                GLib.idle_add(progressbar.set_fraction, perc)
            except Exception as e:
                print(e)
            time.sleep(1)

    def download_setting_thread(self, handler: Handler, setting: dict, button: Gtk.Button, progressbar: Gtk.ProgressBar):
        self.model_threads[(setting["key"], handler.key)][1] = threading.current_thread().ident
        self.downloading[(setting["key"], handler.key)] = True
        th = threading.Thread(target=self.update_download_status_setting, args=(handler, setting, progressbar))
        th.start()
        setting["callback"](setting["key"])
        icon = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="user-trash-symbolic"))
        icon.set_icon_size(Gtk.IconSize.INHERIT)
        button.add_css_class("error")
        button.set_child(icon)
        self.downloading[(setting["key"], handler.key)] = False

    def create_web_button(self, website, folder=False) -> Gtk.Button:
        """Create an icon to open a specified website or folder

        Args:
            website (): The website/folder path to open
            folder (): if it is a folder, defaults to False

        Returns:
            The created button
        """
        wbbutton = Gtk.Button(icon_name="internet-symbolic" if not folder else "search-folder-symbolic")
        wbbutton.add_css_class("flat")
        wbbutton.set_valign(Gtk.Align.CENTER)
        wbbutton.set_name(website)
        if not folder:
            wbbutton.connect("clicked", lambda _: open_website(website))
        else:
            wbbutton.connect("clicked", lambda _: open_folder(website))
        return wbbutton

    def show_flatpak_sandbox_notice(self, el=None):
        """Create a MessageDialog that explains the issue with missing permissions on flatpak

        Args:
            el (): 
        """
        # Create a modal window with the warning
        dialog = Adw.MessageDialog(
            title="Permission Error",
            modal=True,
            transient_for=self,
            destroy_with_parent=True
        )

        # Imposta il contenuto della finestra
        dialog.set_heading(_("Not enough permissions"))

        # Aggiungi il testo dell'errore
        dialog.set_body_use_markup(True)
        dialog.set_body(_("Nyarch Assistant does not have enough permissions to run commands on your system, please run the following command"))
        dialog.add_response("close", _("Understood"))
        dialog.set_default_response("close")
        dialog.set_extra_child(CopyBox("flatpak --user override --talk-name=org.freedesktop.Flatpak --filesystem=home moe.nyarchlinux.assistant", "bash", parent = self))
        dialog.set_close_response("close")
        dialog.set_response_appearance("close", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect('response', lambda dialog, response_id: dialog.destroy())
        # Show the window
        dialog.present()

