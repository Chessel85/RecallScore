# widgets/region1_list_widget.py
from widgets.region_property_list_widget import RegionPropertyListWidget


class Region1ListWidget(RegionPropertyListWidget):
    """
    Region 1 (score info) property list. The only behaviour beyond the
    shared base is routing Ctrl+Tab / Ctrl+Shift+Tab to the section tab
    bar sitting above it, so a multi-section score's sections can be
    stepped through without first moving focus onto the bar - kept as its
    own file/class so Region 1 has the same one-file-per-region shape as
    Region2ListWidget/TimelineListWidget/Region5ListWidget.
    """

    def _region_ctrl_tab(self, forward: bool) -> bool:
        tabs = getattr(self.window(), "region_1_section_tabs", None)
        if tabs is None:
            return False
        return tabs.step(1 if forward else -1)
