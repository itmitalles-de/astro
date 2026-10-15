# SPDX-License-Identifier: GPL-3.0-or-later
"""Private smoke-test kitten; never installed into the owner's configuration."""
from kittens.tui.handler import result_handler


def main(args):
    return None


@result_handler(no_ui=True)
def handle_result(args, answer, target_window_id, boss):
    import json
    import os
    from pathlib import Path
    import runpy
    from kitty import fast_data_types as fdt

    if os.environ.get('ASTRO_QA_ISOLATED') != '1':
        raise RuntimeError('This probe is only for the private smoke-test instance')
    window=boss.window_id_map[target_window_id]
    if '--seed-legacy-pointer' in args:
        import ctypes
        from types import SimpleNamespace
        state=getattr(boss,'_kitty_pane_buttons_state_v1')
        previous=state.pop('pointer',None)
        if callable(getattr(previous,'close',None)):previous.close()
        lib=ctypes.CDLL('libX11.so.6')
        lib.XOpenDisplay.argtypes=[ctypes.c_char_p];lib.XOpenDisplay.restype=ctypes.c_void_p
        legacy=SimpleNamespace(_lib=lib,_display=lib.XOpenDisplay(None),query=lambda xid: None)
        assert legacy._display
        boss._astro_qa_legacy_pointer=state['pointer']=legacy
        return json.dumps({'legacy_connection_created':True})
    if '--verify-legacy-release' in args:
        legacy=boss._astro_qa_legacy_pointer
        state=getattr(boss,'_kitty_pane_buttons_state_v1')
        return json.dumps({'legacy_connection_released':legacy._display is None and state.get('pointer') is not legacy})
    if '--probe-pointer' in args:
        module=runpy.run_path(str(Path(os.environ['KITTY_CONFIG_DIRECTORY'])/'window_title_bar.py'))
        pointer=module['_X11Pointer']()
        try:
            valid=pointer.query(fdt.x11_window_id(window.os_window_id))
            invalid=pointer.query(0xffffffff)
            return json.dumps({'valid_pointer':valid is not None,'invalid_pointer':invalid})
        finally:
            if hasattr(pointer,'close'):pointer.close()
    tab=window.tabref()
    state=getattr(boss,'_kitty_pane_buttons_state_v1')
    state['expanded'].add(window.id)
    tab.update_window_title_bars()
    bar=window._title_bar_screen
    size=fdt.get_os_window_size(window.os_window_id)
    scale=size['framebuffer_width']/size['width']
    controls={name:{'x':(bar.geometry.left+(start+end)*bar.cell_width/2)/scale,
                    'y':(bar.geometry.top+bar.geometry.bottom)/2/scale}
              for name,start,end,label in state['cells'].get(window.id,[])}
    windows=[{'id':w.id,'pid':w.child.pid,'cwd':w.cwd_of_child,
              'left':w.geometry.left,'top':w.geometry.top,
              'right':w.geometry.right,'bottom':w.geometry.bottom}
             for w in tab.windows]
    return json.dumps({'root':tab.current_layout.pairs_root.serialize(),
                       'buttons':controls,'windows':windows,'source':window.id})
