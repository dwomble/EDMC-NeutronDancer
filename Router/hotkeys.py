from utils.debug import Debug, catch_exceptions
from utils.misc import singleton, copy_to_clipboard
from .context import Context

try:
    import EDMCHotkeys as hotkeys #type: ignore
except ImportError:
    Debug.logger.warning(f"EDMC Hotkeys not installed")
    hotkeys = None


@singleton
class Hotkeys:
    """
    Hotkey manager.
    """

    def __init__(self) -> None:
        if not hotkeys: return

        for cmd in ["next", "previous", "copy"]:
            if not hotkeys.register_action(
                hotkeys.Action(id=f"{Context.plugin_name}-{cmd}",
                            label=cmd,
                            plugin=Context.plugin_name,
                            callback=getattr(self, cmd),
                            thread_policy="main",
                            cardinality="single"
                            )):
                Debug.logger.debug(f"Error registering {cmd} hotkey")

    @staticmethod
    def next(*, payload=None, source="hotkey", hotkey=None) -> None:
        if Context.route.route == []: return
        Context.router.update_route(1)
    @staticmethod
    def previous(*, payload=None, source="hotkey", hotkey=None) -> None:
        if Context.route.route == []: return
        Context.router.update_route(-1)
    @staticmethod
    def copy(*, payload=None, source="hotkey", hotkey=None) -> None:
        if Context.route.route == []: return
        copy_to_clipboard(Context.ui.parent, Context.route.next_stop())