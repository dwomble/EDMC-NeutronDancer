from email import message
import json
from dataclasses import dataclass, asdict
from functools import partial
from threading import Thread, Event
from math import floor
from datetime import datetime, timedelta
from copy import deepcopy

import tkinter as tk
from tkinter import font, colorchooser as tkColorChooser
import myNotebook as nb # type: ignore

from config import config # type: ignore
#from edmc_data import GuiFocusNoFocus, FlagsInMainShip, GuiFocusGalaxyMap # type: ignore
import edmc_data # type: ignore

from .utils.debug import Debug, catch_exceptions
from .utils.misc import singleton, hfplus, str_truncate
from .context import Context
from .constants import OVERLAY_PROGRESS_DEFAULT, CarrierStates, lbls, ovr, cnf, errs

try:
    from EDMCOverlay import edmcoverlay # type: ignore
    from overlay_plugin.overlay_api import define_plugin_group # type: ignore
except ImportError:
    Debug.logger.warning(f"EDMC Overlay not installed")
    edmcoverlay = None
    define_plugin_group = None

#FLAGS = [edmc_data.FlagsDocked, edmc_data.FlagsLanded, edmc_data.FlagsLandingGearDown, edmc_data.FlagsShieldsUp, edmc_data.FlagsSupercruise,
#         edmc_data.FlagsFlightAssistOff, edmc_data.FlagsHardpointsDeployed, edmc_data.FlagsInWing]
@dataclass
class OvFrame:
    """ Overlay frame details """
    name:str = 'Default'
    enabled:bool = True # Preference state
    visible:bool = True # Current visibility state
    x:int = 100
    y:int = 100
    text_colour:str = "#ffffff"
    ttl:int = 0

@singleton
class Overlay():
    """
    Overlay frame manager.
    """

    def __init__(self) -> None:
        self.progress_bar:bool = config.get_bool(f"{Context.plugin_name}_progress_bar", True)
        self.progress_display:str = config.get(f"{Context.plugin_name}_progress_display", OVERLAY_PROGRESS_DEFAULT)
        self.ovfrs:dict[str, OvFrame] = {'Default': OvFrame('Default', x = 100, y = 900),
                                         'Galaxy Map': OvFrame('Galaxy Map', x = 500, y = 200),
                                         'Carrier': OvFrame('Carrier', x = 1000, y = 900),
                                         'Alert': OvFrame('Alert', x = 640, y = 670, ttl=15)
                                         }
        self.stoppers:dict[str, Event] = {}

        self._load_prefs()

        for k, fr in self.ovfrs.items():
            fr.name = k
            self.create_frame(Context.plugin_name, fr)

        self.msgs:dict = {}


    def _get_overlay(self):
        """ Is an overlay installed and running? """
        if not edmcoverlay: return

        # Is it running?
        try:
            return edmcoverlay.Overlay()
        except Exception as e:
            Debug.logger.warning(f"EDMCOverlay is not running {e}")
            return

    @catch_exceptions
    def update_overlays(self) -> None:
        """ Update overlay after a waypoint """
        if not self._get_overlay(): return

        if Context.route.route == []:
            self.clear_frame('Default')
            self.clear_frame('Galaxy Map')
            self.clear_frame('Alert')
            if Context.router.carrier_state == CarrierStates.Idle:
                self.clear_frame('Carrier')
            return

        primary:str = Context.route.next_stop_display()
        detail:str = Context.route.next_stop_station()
        wp:str = f"{primary} · {detail}" if detail else primary
        if Context.route.jumps_to_wp() != 0:
            wp += f" ({Context.route.jumps_to_wp()} {lbls['jumps'] if Context.route.jumps_to_wp() != 1 else lbls['jump']})"
        # 40 is a guessed overlay width -- adjust if it looks off in-game.
        wp = str_truncate(wp, length=40, loc='right')

        message:list = [{'size': 'large', 'text' : "Next: " + str(wp)}]

        # Galaxy map frame just shows next jump
        self.update_frame('Galaxy Map', message, ttl=120)

        if Context.route.fleetcarrier:
            self.display_carrier('Idle', 120, destination=primary)
            return

        if self.progress_bar:
            prog:int = round(Context.route.perc_jumps_rem())
            if Context.route.total_dist() > 0:
                prog = round(Context.route.perc_dist_rem())
            if Context.route.jumps_remaining() == 0:
                prog = 100

            message.insert(0, {'progressbar': prog, 'width': 200,'colour': self.ovfrs['Default'].text_colour})

        if Context.route.tracks_refuel_or_neutron():
            # The following variables are available for the progress display:
                # Jumps completed {jc}
                # Jumps remaining {jr}
                # Jumps total {jt}

                # Distance to next checkpoint. {dc}
                # Distance remaining {dr}
                # Distance total {dt}

                # Distance per hour {dh}
                # Jumps per hour {jh}

                # Refuel jumps {rj}
                # Distance (or jumps) to next refuel {rd}
                # Refuel message {rs}

                # Star type next stop {st}

            jc:str = hfplus(tuple([Context.route.total_jumps() - Context.route.jumps_remaining(), 'int', '-' if Context.route.offset < 0 else '0']))
            jr:str = hfplus(tuple([Context.route.jumps_remaining(), 'int', '0']))
            jt:str = hfplus(tuple([Context.route.total_jumps(), 'int']))

            dc:str = hfplus(tuple([Context.route.total_dist() - Context.route.dist_remaining(), 'float', '0']))
            dr:str = hfplus(tuple([Context.route.dist_remaining(), 'float', '0']))
            dt:str = hfplus(tuple([Context.route.total_dist(), 'float', '0']))

            dh:str = hfplus(tuple([Context.route.dist_per_hour(), 'float', '-']))
            jh:str = hfplus(tuple([Context.route.jumps_per_hour(), 'float', '-']))

            rj:str = hfplus(tuple([Context.route.jumps_to_refuel(), 'int', '-']))
            rd:str = hfplus(tuple([Context.route.dist_to_refuel(), 'float', '-']))

            rs:str = lbls["next_refuel"].format(rd=rd) if rd != '-' else ""

            # or: ✨ ◄ ⭐ ► ◄ 𐫰 ► 🌀 ⚛
            st:str = "⛽" if Context.route.jumps_to_refuel() == 0 else "🌀" if Context.route.is_neutron() else "✨"

            try:
                message.append({'size': "normal", 'text': self.progress_display.format(jc=jc, jr=jr, jt=jt, dc=dc, dr=dr, dt=dt, dh=dh, jh=jh, rj=rj, rd=rd, rs=rs, st=st)})
            except Exception as e:
                Debug.logger.warning(f"Error formatting progress display: {e}")
                message.append({'size': "normal", 'text': errs["format_error"]})
        else:
            # No refuel/neutron columns -- show detail lines instead of the template.
            detail_lines:list = Context.route.next_stop_details()
            if detail_lines:
                message.append({'size': "normal", 'text': "\n".join(detail_lines)})

        self.update_frame('Default', message, ttl=120)

        if Context.route.refuel() and not Context.route.fuel_full:
            self.display_alert(ovr["refuel"])
        elif Context.route.is_neutron() == True:
            Context.overlay.display_alert(ovr["neutron"])
        elif Context.route.refuel() and Context.route.fuel_full and not Context.route.is_neutron():
            self.clear_frame("Alert")


    def display_carrier(self, type:str, end:datetime|int = 120, destination:str = '') -> None:
        """ Display carrier arrival info """
        cstr:str = ''

        self.stop_countdown('Carrier')
        match type:
            case 'Carrier':
                cstr = ovr['jump'].format(d=destination, t='{t}')
            case 'SquadronCarrier':
                cstr = 'Squadron ' + ovr['jump'].format(d=destination, t='{t}')
            case 'Cooldown':
                cstr = ovr['cooldown']
            case 'Idle':
                cstr = ovr['idle'].format(d=destination)

        self.display_countdown('Carrier', [{'size': 'large', 'text' : cstr}], end)


    def display_alert(self, message:str = '') -> None:
        """ Display an alert message """
        self.show_frame('Alert')
        self.update_frame('Alert', [{'size': 'large', 'text' : message}], ttl=5)


    def redraw_frames(self) -> None:
        """ Redraw all overlay frames """
        [self.redraw_frame(fr) for fr in self.msgs]


    def redraw_frame(self, frame:str = "") -> None:
        overlay = self._get_overlay()
        if not overlay or frame not in self.msgs or not self.ovfrs[frame].visible or not self.ovfrs[frame].enabled: return
        [overlay.send_message(**m) if 'msgid' in m else overlay.send_shape(**m) for m in self.msgs[frame].values()]


    def clear_frames(self) -> None:
        """ Clear all overlay frames """
        [self.clear_frame(fr) for fr in self.ovfrs]


    def clear_frame(self, frame:str = "") -> None:
        """ Hide a frame and clear it so it doesn't show again """
        self.hide_frame(frame)
        if frame in self.msgs:
            del self.msgs[frame]


    def hide_frames(self) -> None:
        """ Hide all overlay frames """
        [self.hide_frame(fr) for fr in self.ovfrs]


    @catch_exceptions
    def hide_frame(self, frame:str = "") -> None:
        """ Clear a message frame """
        overlay = self._get_overlay()
        if not overlay or frame not in self.msgs: return

        self.ovfrs[frame].visible = False
        for m in self.msgs[frame].values():
            tmp:dict = deepcopy(m)
            tmp['ttl'] = 1
            if tmp.get('msgid'):
                tmp['text'] = ''
                overlay.send_message(**tmp)
            if tmp.get('shapeid'):
                tmp['fill'] = '#00000000'
                tmp['color'] = '#00000000'
                overlay.send_shape(**tmp)

    def show_frames(self) -> None:
        """ Show all overlay frames """
        [self.show_frame(fr) for fr in self.ovfrs]

    def show_frame(self, frame:str = "") -> None:
        """ Show a message frame """
        overlay = self._get_overlay()
        if not overlay or frame not in self.msgs or not self.ovfrs[frame].enabled: return

        self.ovfrs[frame].visible = True
        for m in self.msgs[frame].values():
            tmp:dict = deepcopy(m)
            if tmp.get('msgid'):
                overlay.send_message(**tmp)
            if tmp.get('shapeid'):
                overlay.send_shape(**tmp)

    @catch_exceptions
    def create_frame(self, group:str, ovf:OvFrame) -> None:
        """ Initialize a frame """
        if not self._get_overlay() or not define_plugin_group: return

        kw:dict = {
            'plugin_group': group,
            'matching_prefixes': f"{group}-",
            'id_prefix_group': f"{group} {ovf.name}",
            'id_prefixes': [f"{group}-{ovf.name}-"],
            'plugin_group_anchor': "nw",
            'payload_justification': "left",
            'marker_label_position': "below",
            'controller_preview_box_mode': "last",
        }
        define_plugin_group(**kw)


    @catch_exceptions
    def update_frame(self, frame:str = "", content:str|list[dict] = "", size:str = "normal", ttl:int = 120) -> None:
        """ Update a frame with a set of messages. If its visible the display it otherwise just store it for later. """

        overlay = self._get_overlay()
        if not overlay or frame not in self.ovfrs: return
        fr:OvFrame = self.ovfrs[frame]

        if isinstance(content, str): content = [{'size': size, 'text': content}]

        self.msgs[frame] = {}
        y:int = 0
        for i, c in enumerate(content):
            if frame not in self.msgs: self.msgs[frame] = {}
            id:str = f"{Context.plugin_name}-{frame}-{i}"
            args:dict = {
                'x': 0,
                'y': y,
                'ttl': c.get('ttl', ttl) # @TODO: ttl needs to be a datetime
            }
            if 'progressbar' in c:
                args['shapeid'] = id + "-a"
                args['shape'] = 'rect'
                args['color'] = c.get('colour', fr.text_colour)
                args['fill'] = '#00000000'
                args['w'] = c.get('width', 100)
                args['h'] = c.get('height', 12)
                if fr.visible == True and fr.enabled == True:
                    overlay.send_shape(**args)
                self.msgs[frame][args['shapeid']] = args

                argsb:dict = deepcopy(args)
                argsb['shapeid'] = id + "-b"
                argsb['shape'] = 'rect'
                argsb['color'] = c.get('colour', fr.text_colour)
                argsb['fill'] = c.get('colour', fr.text_colour)
                argsb['w'] = int(c.get('progressbar', 0) * c.get('width', 100) / 100)
                argsb['h'] = c.get('height', 12)
                if fr.visible == True and fr.enabled == True:
                    overlay.send_shape(**argsb)
                self.msgs[frame][argsb['shapeid']] = argsb
                y += 20
            else:
                args['msgid'] = id
                args['text'] = c.get('text', '')
                args['color'] = c.get('colour', fr.text_colour)
                args['size'] = c.get('size', 'normal')
                #Debug.logger.debug(f"Overlay {frame} message {args} {fr.enabled} {fr.visible}")
                if fr.visible == True and fr.enabled == True:
                    overlay.send_message(**args)
                self.msgs[frame][args['msgid']] = args
                y += 25 if args['size'] == 'large' else 20


    def _timedelta_str(self, delta:timedelta) -> str:
        """ Display remaining time showing hh:mm:ss """
        s:int = delta.seconds
        unit:int = 60
        res:list = []
        while unit > 0:
            t, s = divmod(s, unit)
            unit = int(unit / 60)
            if t > 0 or unit < 3600:
                res.append(f"{t:02d}")
        return ':'.join(res)


    @catch_exceptions
    def _countdown(self, frame:str, content:str|list[dict], end:datetime, stop:Event) -> None:
        """ Update the countdown display frame until zero or stopped """
        rem:timedelta = end - datetime.now(tz=end.tzinfo)
        while rem.total_seconds() > 0 and not stop.wait(1):
            rem = end - datetime.now(tz=end.tzinfo)
            display:list|str = [{k:v.format(t=self._timedelta_str(rem)) for k, v in c.items()} for c in content] \
                if isinstance(content, list) else content.format(t=self._timedelta_str(rem))
            self.update_frame(frame, display, ttl=1)

        stop.clear()
        self.update_frame(frame, '', ttl=1)
        #Debug.logger.debug("Countdown thread is ending.")


    def stop_countdown(self, frame:str) -> None:
        """ Stop a countdown display for a frame """
        if frame not in self.stoppers: return
        self.stoppers[frame].set()


    def stop_countdowns(self) -> None:
        """ Stop every active countdown thread -- call on shutdown so background threads don't outlive the app """
        for frame in list(self.stoppers.keys()):
            self.stop_countdown(frame)


    @catch_exceptions
    def display_countdown(self, frame:str, content:str|list[dict], end:datetime|int|None) -> None:
        """
        Like display message but with a countdown either until a specific time or for some number of seconds
        The countdown should be in a variable t in the content string
        """
        Debug.logger.debug(f"Countdown starting {content} {end}")
        if end == None or frame not in self.ovfrs: return
        self.stop_countdown(frame)
        self.stoppers[frame] = Event()
        if isinstance(end, int): end = datetime.now() + timedelta(seconds=end)
        Thread(target=self._countdown, args=(frame, content, end, self.stoppers[frame]), daemon=True,
               name=f"{Context.plugin_name}_{frame} overlay countdown worker").start()


    @catch_exceptions
    def dashboard_entry(self, cmdr:str, is_beta:bool, entry:dict) -> None:
        """ ED UI state change, store the current state """

        # Default frame, visible in ship main view only
        # Galaxy Map frame, visible in galaxy map only
        if not Context.route or not (bool(entry["Flags"] & edmc_data.FlagsInMainShip)):
            self.hide_frame('Default')
            self.hide_frame('Galaxy Map')
        elif entry.get("GuiFocus") in (edmc_data.GuiFocusNoFocus, edmc_data.GuiFocusExternalPanel):
            self.show_frame('Default')
            self.hide_frame('Galaxy Map')
        elif entry.get("GuiFocus") == edmc_data.GuiFocusGalaxyMap:
            self.hide_frame('Default')
            self.show_frame('Galaxy Map')
        else:
            self.hide_frame('Default')
            self.hide_frame('Galaxy Map')

        # Carrier frame, visible in ship main view only
        if not bool(entry["Flags"] & edmc_data.FlagsInMainShip) or \
            entry.get("GuiFocus") != edmc_data.GuiFocusNoFocus:
            self.hide_frame('Carrier')
        else:
            self.show_frame('Carrier')


    @catch_exceptions
    def prefs_display(self, parent:nb.Frame) -> nb.Frame:
        """ EDMC settings pane hook. Displays one frame per row. """

        def bind_var(data_obj, attribute, tk_var):
            # Update dataclass whenever the UI changes
            def update_obj(*args) -> None:
                setattr(data_obj, attribute, tk_var.get())

            tk_var.trace_add("write", update_obj)
            return tk_var

        def colour_picker(parent:nb.Frame, frame:str, which:str, col:tk.StringVar) -> None:
            (_, color) = tkColorChooser.askcolor(col.get(), title=which, parent=parent)

            if color:
                col.set(color)
                cbtns[frame].config(**{which.lower(): color})

        def validate_int(val:str) -> bool:
            return True if val.isdigit() or val == '' else False

        pref_opts:list = [
            ('enabled', cnf["enable"], tk.BooleanVar, nb.Checkbutton),
            ('text_colour', cnf["foreground"], tk.StringVar, 'ColorPicker'),
            ]

        # Hide existing messages. Redraw them in the new location when the user clicks save
        self.hide_frames()

        ovrprefs:nb.Frame = nb.Frame(parent)
        ovrprefs.columnconfigure(6, weight=1)
        ovrprefs.rowconfigure(60, weight=1)
        ovrprefs.grid()

        props = font.Font(name="TkDefaultFont", exists=True).actual()
        props["weight"] = "bold"
        bold:font.Font = font.Font(**props)

        row:int = 0; col:int = 0
        nb.Label(ovrprefs, text=cnf["overlays"], justify=tk.LEFT, font=bold).grid(row=row, column=0, padx=10, sticky=tk.NW); row += 1

        row += 1; col = 1
        # Loop through the frames and create a preferences line for each
        vars:dict = {}; cbtns:dict = {}
        for name, fr in self.ovfrs.items():
            nb.Label(ovrprefs, text=name, justify=tk.LEFT).grid(row=row, column=col, padx=10, pady=5, sticky=tk.W)
            col += 1
            for k in pref_opts:
                var = bind_var(fr, k[0], k[2](value=getattr(fr, k[0])))
                vars[f"{name}-{k[0]}"] = var
                match k[3]:
                    case nb.Checkbutton:
                        nb.Checkbutton(ovrprefs, text=k[1], variable=var).grid(row=row, column=col, padx=10, pady=0, sticky=tk.W)
                    case 'ColorPicker':
                        btn:tk.Button = tk.Button(ovrprefs, text=k[1], foreground=fr.text_colour, background="#555555",
                                                  command=partial(colour_picker, ovrprefs, name, k[1], var))
                        btn.grid(row=row, column=col, padx=5, pady=0, sticky=tk.W)
                        cbtns[name] = btn
                col += 1

        row += 1; col = 0
        nb.Label(ovrprefs, text=cnf["controller"], justify=tk.LEFT).grid(row=row, column=col, columnspan=9, padx=10, pady=5, sticky=tk.W)

        row += 1; col = 0
        nb.Label(ovrprefs, text=cnf["default_overlay"], justify=tk.LEFT).grid(row=row, column=col, padx=10, sticky=tk.NW)
        row += 1; col = 0
        nb.Label(ovrprefs, text=cnf["progress_bar"], justify=tk.LEFT).grid(row=row, column=col, padx=10, sticky=tk.NW)
        col += 1
        self.pb:tk.BooleanVar = tk.BooleanVar(value=self.progress_bar)
        nb.Checkbutton(ovrprefs, text="Enable", variable=self.pb).grid(row=row, column=col, padx=5, pady=0, sticky=tk.W)

        row += 1; col = 0
        nb.Label(ovrprefs, text=cnf["progress_display"], justify=tk.LEFT).grid(row=row, column=col, padx=10, sticky=tk.NW)
        col += 1
        self.pv:tk.StringVar = tk.StringVar(value=self.progress_display.replace('\n', '\\n'))
        nb.EntryMenu(ovrprefs, width=80, textvariable=self.pv).grid(row=row, column=col, columnspan=8, padx=5, pady=0, sticky=tk.W)

        return ovrprefs

    @catch_exceptions
    def save_prefs(self) -> bool:
        """ Serialize and save the frames dictionary to EDMC config. """
        # Store the serialized frames in the config

        for name, fr in self.ovfrs.items():
            config.set(f"{Context.plugin_name}_{name}_overlay", json.dumps(asdict(fr)))
        self.progress_bar = self.pb.get()
        config.set(f"{Context.plugin_name}_progress_bar", self.progress_bar)
        self.progress_display = self.pv.get().replace('\\n', '\n')
        config.set(f"{Context.plugin_name}_progress_display", self.progress_display)

        self.update_overlays()
        self.redraw_frames()

        Debug.logger.info(f"Saved frames to EDMC config")
        return True


    @catch_exceptions
    def _from_dict(self, name, data:dict) -> None:
        self.ovfrs[name] = OvFrame(**data)


    @catch_exceptions
    def _load_prefs(self) -> None:
        """ Read frame data from the EDMC config. """

        for name in self.ovfrs:
            conf:str|None = config.get(f"{Context.plugin_name}_{name}_overlay")
            if conf == None: continue
            data:dict = json.loads(conf)
            try:
                self.ovfrs[name] = OvFrame(**data)
            except:
                pass
