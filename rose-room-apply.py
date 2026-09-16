#!/usr/bin/env python3
"""Apply Dice's SUNSET ROSE selection to Kitty and RMPC 0.11.
Run: python3 rose-room-apply.py
Check only: python3 rose-room-apply.py --check
Undo: python3 rose-room-apply.py --restore
No packages, MPD settings, audio inputs, wallpaper, or key mappings are changed.
Native layout approximates the HTML: 60% top / 40% queue; 52% artwork / 48% metadata+CAVA.
17.7 pt approximates the 'large' preview. CSS pixel sizes, simulated CAVA and per-element
font sizing cannot be reproduced literally in terminal cells. Restart the apps after applying.
Bright ANSI variants are derived because the preview defines only a partial ANSI palette.
Sources: https://sw.kovidgoyal.net/kitty/conf/
https://github.com/mierak/rmpc/tree/v0.11.0/src/config
"""
import argparse, hashlib, json, os, re, shutil, stat, subprocess, tempfile
from datetime import datetime
from pathlib import Path

THEME_TEXT = '#![enable(implicit_some)]\n#![enable(unwrap_newtypes)]\n#![enable(unwrap_variant_newtypes)]\n(\n    default_album_art_path: None,\n    format_tag_separator: " | ",\n    browser_column_widths: [20, 38, 42],\n    background_color: None,\n    text_color: Some("#E9D9E2"),\n    header_background_color: None,\n    modal_background_color: Some("#281923"),\n    modal_backdrop: false,\n    preview_label_style: (fg: "#C74D82"),\n    preview_metadata_group_style: (fg: "#B6A5BA", modifiers: "Bold"),\n    highlighted_item_style: (fg: "#C74D82", modifiers: "Bold"),\n    current_item_style: (fg: "#C74D82", bg: "#563348", modifiers: "Bold"),\n    borders_style: (fg: "#82566E"),\n    highlight_border_style: (fg: "#C74D82"),\n    symbols: (\n        song: "S",\n        dir: "D",\n        playlist: "P",\n        marker: "M",\n        ellipsis: "...",\n        song_style: None,\n        dir_style: None,\n        playlist_style: None,\n    ),\n    level_styles: (\n        info: (fg: "#C74D82", bg: "#281923"),\n        warn: (fg: "#C74D82", bg: "#281923"),\n        error: (fg: "#D99C9F", bg: "#281923"),\n        debug: (fg: "#C4A4CC", bg: "#281923"),\n        trace: (fg: "#8E4063", bg: "#281923"),\n    ),\n    progress_bar: (\n        symbols: ["╺", "━", "●", "─", "╸"],\n        track_style: (fg: "#82566E"),\n        elapsed_style: (fg: "#C74D82"),\n        thumb_style: (fg: "#C74D82"),\n        use_track_when_empty: true,\n    ),\n    scrollbar: (\n        symbols: ["│", "█", "▲", "▼"],\n        track_style: (),\n        ends_style: (),\n        thumb_style: (fg: "#C74D82"),\n    ),\n    tab_bar: (\n        active_style: (fg: "#C74D82", bg: "#563348", modifiers: "Bold"),\n        inactive_style: (fg: "#B6A5BA"),\n    ),\n    lyrics: (\n        timestamp: false\n    ),\n    cava: (\n        bar_symbols: [\'▁\', \'▂\', \'▃\', \'▄\', \'▅\', \'▆\', \'▇\', \'█\'],\n        inverted_bar_symbols: [\'▔\', \'▔\', \'▀\', \'▀\', \'▀\', \'█\', \'█\', \'█\'],\n        bg_color: None,\n        bar_color: Gradient({\n            0: "#563348",\n            45: "#8E4063",\n            75: "#C74D82",\n            100: "#C74D82",\n        }),\n        bar_spacing: 0,\n        bar_width: 1,\n        orientation: Bottom,\n    ),\n    browser_song_format: [\n        (\n            kind: Group([\n                (kind: Property(Track)),\n                (kind: Text(" ")),\n            ])\n        ),\n        (\n            kind: Group([\n                (kind: Property(Artist)),\n                (kind: Text(" - ")),\n                (kind: Property(Title)),\n            ]),\n            default: (kind: Property(Filename))\n        ),\n    ],\n    song_table_format: [\n        (\n            prop: (kind: Property(Artist),\n                default: (kind: Text("Unknown"))\n            ),\n            label_prop: (kind: Text("Artist"), style: (fg: "#C74D82")),\n            width: "24%",\n        ),\n        (\n            prop: (kind: Property(Title),\n                default: (kind: Text("Unknown"))\n            ),\n            label_prop: (kind: Text("Title"), style: (fg: "#C74D82")),\n            width: "45%",\n        ),\n        (\n            prop: (kind: Property(Album), style: (fg: "#E9D9E2"),\n                default: (kind: Text("Unknown Album"), style: (fg: "#E9D9E2"))\n            ),\n            label_prop: (kind: Text("Album"), style: (fg: "#C74D82")),\n            width: "18%",\n        ),\n        (\n            prop: (kind: Property(Duration),\n                default: (kind: Text("-"))\n            ),\n            label_prop: (kind: Text("Duration"), style: (fg: "#C74D82")),\n            width: "8",\n            alignment: Right,\n        ),\n    ],\n    layout: Split(direction: Vertical, panes: [\n        (size: "3", borders: "BOTTOM", pane: Component("rose-header")),\n        (size: "2", borders: "BOTTOM", pane: Pane(Tabs)),\n        (size: "1", pane: Pane(Empty())),\n        (size: "100%", pane: Pane(TabContent)),\n        (size: "2", borders: "TOP", pane: Component("rose-footer")),\n    ]),\n    components: {\n        "rose-header": Split(direction: Horizontal, panes: [\n(size: "29", pane: Component("header_left")),\n(size: "100%", pane: Component("header_center")),\n(size: "24", pane: Component("header_right")),\n]),\n        "rose-footer": Split(direction: Horizontal, panes: [\n(size: "10", borders: "RIGHT", pane: Component("input_mode")),\n(size: "2", pane: Pane(Empty())),\n(size: "100%", pane: Component("progress_bar")),\n(size: "2", pane: Pane(Empty())),\n(size: "34", pane: Pane(Property(content: [(kind: Property(Status(Elapsed))), (kind: Text(" / "), style: (fg: "#B6A5BA")), (kind: Property(Status(Duration))), (kind: Text("  [p:play q:quit ?:help]"), style: (fg: "#B6A5BA"))], align: Right))),\n]),\n        "rose-now": Split(direction: Vertical, panes: [\n(size: "1", pane: Pane(Property(content: [(kind: Text("Now Playing"), style: (fg: "#C74D82", modifiers: "Bold"))], align: Left))),\n(size: "1", pane: Pane(Empty())),\n(size: "1", pane: Pane(Property(content: [(kind: Property(Song(Title)), style: (fg: "#E9D9E2"), default: (kind: Text("No Song")))], align: Left))),\n(size: "1", pane: Pane(Property(content: [(kind: Property(Song(Artist)), style: (fg: "#B6A5BA"), default: (kind: Text("Unknown Artist")))], align: Left))),\n(size: "1", pane: Pane(Property(content: [(kind: Property(Song(Album)), style: (fg: "#B6A5BA"), default: (kind: Text("Unknown Album")))], align: Left))),\n(size: "1", pane: Pane(Property(content: [(kind: Property(Status(SampleRate()))), (kind: Text(" Hz / "), style: (fg: "#B6A5BA")), (kind: Property(Song(FileExtension)))], align: Left))),\n(size: "100%", pane: Pane(Empty())),\n]),\n        "rose-queue": Split(direction: Vertical, panes: [\n            (size: "60%", pane: Split(direction: Horizontal, panes: [\n                (size: "52%", pane: Split(direction: Horizontal, panes: [\n                    (size: "100%", pane: Pane(AlbumArt)),\n                    (size: "2", pane: Pane(Empty())),\n                ])),\n                (size: "48%", borders: "LEFT", pane: Split(direction: Horizontal, panes: [\n                    (size: "2", pane: Pane(Empty())),\n                    (size: "100%", pane: Split(direction: Vertical, panes: [\n                        (size: "7", pane: Component("rose-now")),\n                        (size: "100%", borders: "TOP", border_title: [(kind: Text(" CAVA "), style: (fg: "#B6A5BA"))], pane: Pane(Cava)),\n                    ])),\n                ])),\n            ])),\n            (size: "40%", borders: "TOP", border_title: [(kind: Text(" Queue "), style: (fg: "#B6A5BA"))], pane: Pane(Queue)),\n        ]),\n\n        "state": Pane(Property(\n            content: [\n                (kind: Text("["), style: (fg: "#C74D82", modifiers: "Bold")),\n                (kind: Property(Status(StateV2( ))), style: (fg: "#C74D82", modifiers: "Bold")),\n                (kind: Text("]"), style: (fg: "#C74D82", modifiers: "Bold")),\n            ], align: Left,\n        )),\n        "title": Pane(Property(\n            content: [\n                (kind: Property(Song(Title)), style: (modifiers: "Bold"),\n                    default: (kind: Text("No Song"), style: (modifiers: "Bold"))),\n            ], align: Center, scroll_speed: 1\n        )),\n        "volume": Split(\n            direction: Horizontal,\n            panes: [\n                (size: "1", pane: Pane(Property(content: [(kind: Text(""))]))),\n                (size: "100%", pane: Pane(Volume(kind: Slider(symbols: (start: None, filled: "─", thumb: "●", track: "─", end: None))))),\n                (size: "3", pane: Pane(Property(content: [(kind: Property(Status(Volume)), style: (fg: "#C74D82"))], align: Right))),\n                (size: "2", pane: Pane(Property(content: [(kind: Text("%"), style: (fg: "#C74D82"))]))),\n            ]\n        ),\n        "elapsed_and_bitrate": Pane(Property(\n            content: [\n                (kind: Property(Status(Elapsed))), \n                (kind: Text(" / ")), \n                (kind: Property(Status(Duration))), \n                (kind: Group([\n                    (kind: Text(" (")), \n                    (kind: Property(Status(Bitrate))), \n                    (kind: Text(" kbps)")),\n                ])),\n            ],\n            align: Left,\n        )),\n        "artist_and_album": Pane(Property(\n            content: [\n                (kind: Property(Song(Artist)), style: (fg: "#C74D82", modifiers: "Bold"),\n                    default: (kind: Text("Unknown"), style: (fg: "#C74D82", modifiers: "Bold"))),\n                (kind: Text(" - ")),\n                (kind: Property(Song(Album)), default: (kind: Text("Unknown Album"))),\n            ], align: Center, scroll_speed: 1\n        )),\n        "states": Split(\n            direction: Horizontal,\n            panes: [\n                (\n                    size: "1",\n                    pane: Pane(Empty())\n                ),\n                (\n                    size: "100%",\n                    pane: Pane(Property(content: [(kind: Property(Status(InputBuffer())), style: (fg: "#C74D82"), align: Left)]))\n                ),\n                (\n                    size: "6",\n                    pane: Pane(Property(content: [\n                        (kind: Text("["), style: (fg: "#C74D82", modifiers: "Bold")),\n                        (kind: Property(Status(RepeatV2(\n                            on_label: "z",\n                            off_label: "z",\n                            on_style: (fg: "#C74D82", modifiers: "Bold"),\n                            off_style: (fg: "#B6A5BA", modifiers: "Dim"),\n                        )))),\n                        (kind: Property(Status(RandomV2(\n                            on_label: "x",\n                            off_label: "x",\n                            on_style: (fg: "#C74D82", modifiers: "Bold"),\n                            off_style: (fg: "#B6A5BA", modifiers: "Dim"),\n                        )))),\n                        (kind: Property(Status(ConsumeV2(\n                            on_label: "c",\n                            off_label: "c",\n                            oneshot_label: "c",\n                            on_style: (fg: "#C74D82", modifiers: "Bold"),\n                            off_style: (fg: "#B6A5BA", modifiers: "Dim"),\n                            oneshot_style: (fg: "#D99C9F", modifiers: "Dim"),\n                        )))),\n                        (kind: Property(Status(SingleV2(\n                            on_label: "v",\n                            off_label: "v",\n                            oneshot_label: "v",\n                            on_style: (fg: "#C74D82", modifiers: "Bold"),\n                            off_style: (fg: "#B6A5BA", modifiers: "Dim"),\n                            oneshot_style: (fg: "#D99C9F", modifiers: "Bold"),\n                        )))),\n                        (kind: Text("]"), style: (fg: "#C74D82", modifiers: "Bold")),\n                        ],\n                        align: Right\n                    ))\n                ),\n            ]\n        ),\n        "input_mode": Pane(Property(\n            content: [\n                (kind: Transform(Replace(content: (kind: Property(Status(InputMode()))), replacements: [\n                    (match: "Normal", replace: (kind: Text(" NORMAL "), style: (fg: "#E9D9E2", bg: "#563348"))),\n                    (match: "Insert", replace: (kind: Text(" INSERT "), style: (fg: "#281923", bg: "#C4A4CC"))),\n                ])))\n            ], align: Center\n        )),\n        "header_left": Split(\n            direction: Vertical,\n            panes: [\n                (size: "1", pane: Component("state")),\n                (size: "1", pane: Component("elapsed_and_bitrate")),\n            ]\n        ),\n        "header_center": Split(\n            direction: Vertical,\n            panes: [\n                (size: "1", pane: Component("title")),\n                (size: "1", pane: Component("artist_and_album")),\n            ]\n        ),\n        "header_right": Split(\n            direction: Vertical,\n            panes: [\n                (size: "1", pane: Component("volume")),\n                (size: "1", pane: Component("states")),\n            ]\n        ),\n        "progress_bar": Split(\n            direction: Horizontal,\n            panes: [\n                (\n                    size: "1",\n                    pane: Pane(Empty())\n                ),\n                (\n                    size: "100%",\n                    pane: Pane(ProgressBar)\n                ),\n                (\n                    size: "1",\n                    pane: Pane(Empty())\n                ),\n            ]\n        )\n    },\n)\n'
TABS_VALUE = '[\n    (name: "Queue", pane: Component("rose-queue")),\n    (name: "Directories", pane: Pane(Directories)),\n    (name: "Artists", pane: Pane(Artists)),\n    (name: "Album Artists", pane: Pane(AlbumArtists)),\n    (name: "Albums", pane: Pane(Albums)),\n    (name: "Playlists", pane: Pane(Playlists)),\n    (name: "Search", pane: Pane(Search)),\n]'
KITTY_TEXT = '# SUNSET ROSE / Dice\'s selected preview\n# Source: https://sw.kovidgoyal.net/kitty/conf/\nbackground #281923\nforeground #E9D9E2\nbackground_opacity 0.55\ndynamic_background_opacity yes\nbackground_image none\ncursor #C74D82\ncursor_text_color #281923\ncursor_shape underline\ncursor_blink_interval 0\nselection_background #563348\nselection_foreground #E9D9E2\nurl_color #B6A5BA\nactive_border_color #C74D82\ninactive_border_color #82566E\nbell_border_color #D7B6A4\ncolor0 #1D1119\ncolor1 #D99C9F\ncolor2 #BEB5AA\ncolor3 #D7B6A4\ncolor4 #B6A5BA\ncolor5 #C4A4CC\ncolor6 #B8ACBF\ncolor7 #E9D9E2\ncolor8 #B6A5BA\ncolor9 #E8AEB1\ncolor10 #D0C7BC\ncolor11 #E7C9B7\ncolor12 #C9B8CD\ncolor13 #D5B8DD\ncolor14 #CCBFD3\ncolor15 #F4E8EE\n# Preview \'large\' is approximated as 15 pt * 1.18; all terminal cells share one font size.\nfont_family JetBrains Mono\nfont_size 17.7\nmodify_font cell_height 120%\nwindow_padding_width 15\nhide_window_decorations titlebar-only\ntab_bar_edge bottom\ntab_bar_min_tabs 1\ntab_bar_style separator\ntab_separator " │ "\ntab_bar_align left\ntab_bar_margin_width 18\ntab_bar_margin_height 12 12\ntab_title_max_length 26\ntab_title_template " {index}  {title[:8] + \'…\' + title[-9:] if title[18:] else title}{fmt.fg._c74d82}{bell_symbol}{activity_symbol}{fmt.fg.tab} "\nactive_tab_title_template none\nactive_tab_font_style bold\ninactive_tab_font_style normal\ntab_activity_symbol " ●"\ntab_bar_show_new_tab_button no\ntab_bar_background #1D1119\ntab_bar_margin_color #1D1119\nactive_tab_background #1D1119\nactive_tab_foreground #C74D82\ninactive_tab_background #1D1119\ninactive_tab_foreground #B6A5BA\n'

def value_span(text, field):
    """Find a top-level RON field, ignoring comments and quoted strings."""
    depth=[]; i=0; root=False
    while i<len(text):
        if text.startswith('//',i):
            end=text.find('\n',i); i=len(text) if end<0 else end+1; continue
        if text.startswith('/*',i):
            level=1; i+=2
            while level and i<len(text):
                if text.startswith('/*',i):level+=1;i+=2
                elif text.startswith('*/',i):level-=1;i+=2
                else:i+=1
            continue
        ch=text[i]
        if ch in ('"', "'"):
            quote=ch;i+=1
            while i<len(text):
                if text[i]=='\\':i+=2
                elif text[i]==quote:i+=1;break
                else:i+=1
            continue
        if ch in '([{':
            depth.append(ch);root=root or (ch=='(' and len(depth)==1);i+=1;continue
        if ch in ')]}':
            if depth:depth.pop()
            i+=1;continue
        if root and depth==['('] and (ch.isalpha() or ch=='_'):
            m=re.match(r'[A-Za-z_][A-Za-z_0-9]*\s*:',text[i:])
            if m and m.group(0).split(':')[0].strip()==field:
                start=i+m.end()
                while text[start].isspace():start+=1
                # Scan the value using a sentinel field to detect its top-level comma.
                j=start; stack=[]; quote=None; comment=0
                while j<len(text):
                    c=text[j]
                    if quote:
                        if c=='\\':j+=2;continue
                        if c==quote:quote=None
                    elif comment:
                        if text.startswith('/*',j):comment+=1;j+=2;continue
                        if text.startswith('*/',j):comment-=1;j+=2;continue
                    elif text.startswith('//',j):
                        end=text.find('\n',j);j=len(text) if end<0 else end+1;continue
                    elif text.startswith('/*',j):comment=1;j+=2;continue
                    elif c in ('"',"'"):quote=c
                    elif c in '([{':stack.append(c)
                    elif c in ')]}':
                        if not stack:return start,j
                        stack.pop()
                    elif c==',' and not stack:return start,j
                    j+=1
                raise ValueError('Unclosed RON field: '+field)
        i+=1
    raise ValueError('Missing top-level field: '+field)

def replace_field(text,field,value):
    start,end=value_span(text,field)
    return text[:start]+value+text[end:]

def digest(data):return hashlib.sha256(data).hexdigest()

def atomic_write(path,data,mode=0o600):
    target=path.resolve()
    fd,tmp=tempfile.mkstemp(prefix='.'+target.name+'-',dir=target.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(data)
        os.chmod(tmp,mode)
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

BEGIN = '# >>> ROSE ROOM SUNSET CINEMA >>>'
END = '# <<< ROSE ROOM SUNSET CINEMA <<<'

def kitty_update(text):
    # Keep the existing config/includes and put this override last.
    if BEGIN in text or END in text:
        if text.count(BEGIN)!=1 or text.count(END)!=1 or text.index(END)<text.index(BEGIN):
            raise ValueError('Malformed Rose Room block; no files changed.')
        start=text.index(BEGIN);end=text.index(END)+len(END)
        text=text[:start]+text[end:]
    return text.rstrip()+'\n\n'+BEGIN+'\n'+KITTY_TEXT+END+'\n'

def native_check(config, theme):
    binary=shutil.which('rmpc')
    if not binary:raise ValueError('rmpc not found. Run this file on your Fedora host, outside ai-box.')
    version=subprocess.run([binary,'version'],capture_output=True,text=True,timeout=10)
    if not re.search(r'\brmpc 0\.11\.',version.stdout+version.stderr):
        raise ValueError('This installer targets RMPC 0.11. Found: '+(version.stdout+version.stderr).strip())
    with tempfile.TemporaryDirectory(prefix='rose-room-check-') as directory:
        root=Path(directory);c=root/'config.ron';t=root/'theme.ron'
        c.write_bytes(config);t.write_bytes(theme)
        result=subprocess.run([binary,'-c',str(c),'-t',str(t),'-a',str(root/'absent-mpd.sock')],capture_output=True,text=True,timeout=20)
        report=result.stdout+'\n'+result.stderr
        if 'Failed to read config' in report or 'Failed to connect to MPD' not in report:
            raise ValueError('RMPC rejected the proposed theme. No settings changed.\n'+report)
    print('PASS: RMPC 0.11 parsed and validated the theme/layout; live MPD was not contacted.')

def file_state(path):
    if not path.exists():return None,0o600
    if not path.is_file():raise ValueError('Not a regular file: '+str(path))
    return path.read_bytes(),stat.S_IMODE(path.stat().st_mode)

def current_hash(path):
    return digest(path.read_bytes()) if path.is_file() else None

def write_record(path,record):atomic_write(path,json.dumps(record,indent=2).encode())

def restore(record_path):
    if not record_path.is_file():raise ValueError('No Rose Room backup found at '+str(record_path))
    record=json.loads(record_path.read_text())
    if record['status']=='restored':print('Already restored.');return
    # Refuse to overwrite edits made after installation, checking every file first.
    for item in record['files']:
        now=current_hash(Path(item['path']))
        if now not in (item['applied_sha256'],item['original_sha256']):
            raise ValueError('Newer edits detected; restore stopped: '+item['path']+'\nBackup: '+item['backup'])
        if item['original_sha256'] is not None and current_hash(Path(item['backup']))!=item['original_sha256']:
            raise ValueError('Backup integrity check failed: '+item['backup'])
    for item in reversed(record['files']):
        target=Path(item['path'])
        if current_hash(target)==item['original_sha256']:continue
        if item['original_sha256'] is None:target.unlink(missing_ok=True)
        else:atomic_write(target,Path(item['backup']).read_bytes(),item['mode'])
    record['status']='restored';write_record(record_path,record)
    print('Previous Kitty and RMPC files restored. Close and reopen the apps.')

def main():
    parser=argparse.ArgumentParser(description='Apply the selected Sunset Rose / cinema theme with backup and rollback.')
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--check',action='store_true');mode.add_argument('--restore',action='store_true')
    parser.add_argument('--kitty-config',type=Path,help='Custom Kitty config path')
    parser.add_argument('--rmpc-config',type=Path,help='Custom RMPC config path')
    args=parser.parse_args()
    base=Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config').expanduser().resolve()
    backup_root=base/'rose-room-backups';record_path=backup_root/'last.json'
    if args.restore:restore(record_path);return
    rmpc=(args.rmpc_config or base/'rmpc'/'config.ron').expanduser().resolve()
    kitty=(args.kitty_config or base/'kitty'/'kitty.conf').expanduser().resolve()
    for path in (rmpc,kitty):
        if not path.is_file():raise ValueError('Missing '+str(path)+'; run on your Fedora host or specify the config path.')
    before_rmpc=rmpc.read_bytes();before_kitty=kitty.read_bytes()
    changed=replace_field(before_rmpc.decode(),'theme','Some("rose-room-sunset-cinema")')
    changed=replace_field(changed,'tabs',TABS_VALUE)
    changed=replace_field(changed,'enable_mouse','true')
    theme=(rmpc.parent/'themes'/'rose-room-sunset-cinema.ron').resolve()
    payloads=[(theme,THEME_TEXT.encode()),(rmpc,changed.encode()),(kitty,kitty_update(before_kitty.decode()).encode())]
    if len({str(path) for path,_ in payloads})!=3:raise ValueError('Configuration paths must be different files.')
    if all(path.is_file() and path.read_bytes()==data for path,data in payloads):
        print('This exact selection is already installed.');return
    if record_path.is_file():
        previous=json.loads(record_path.read_text())
        if previous.get('status') in ('prepared','applied'):
            raise ValueError('An earlier Rose Room application is recorded. Use --restore before applying a different/edit-revised copy. Backups: '+str(backup_root))
    native_check(changed.encode(),THEME_TEXT.encode())
    print('Selection: Sunset Rose, accent #C74D82, opacity 0.55 (45% transparency).')
    print('Kitty: bottom separator tabs, underline cursor, 17.7 pt. RMPC: top artwork/metadata/CAVA, full-width queue below.')
    print('Night backdrop is a preview gradient; desktop wallpaper is unchanged.')
    if args.check:print('Check complete. No configuration files changed.');return
    plans=[]
    for path,data in payloads:
        original,permissions=file_state(path)
        plans.append((path,data,original,permissions))
    # Confirm the source configs did not change during validation.
    if rmpc.read_bytes()!=before_rmpc or kitty.read_bytes()!=before_kitty:
        raise ValueError('A config changed during validation. Run again.')
    backup_root.mkdir(parents=True,exist_ok=True,mode=0o700)
    backup_dir=backup_root/datetime.now().strftime('%Y%m%d-%H%M%S-%f');backup_dir.mkdir(mode=0o700)
    record={'status':'prepared','files':[]}
    for index,(path,data,original,permissions) in enumerate(plans):
        backup=backup_dir/(str(index)+'-'+path.name)
        if original is not None:atomic_write(backup,original)
        record['files'].append({'path':str(path),'backup':str(backup),'mode':permissions,'original_sha256':digest(original) if original is not None else None,'applied_sha256':digest(data)})
    write_record(record_path,record)
    try:
        for path,data,original,permissions in plans:
            if current_hash(path)!=(digest(original) if original is not None else None):raise ValueError('File changed before write: '+str(path))
            path.parent.mkdir(parents=True,exist_ok=True)
            atomic_write(path,data,permissions)
        record['status']='applied';write_record(record_path,record)
    except Exception:
        restore(record_path)
        raise
    print('APPLIED. Backup: '+str(backup_dir))
    print('Close RMPC with q, then close and reopen Kitty and launch rmpc.')
    print('Undo: python3 '+str(Path(__file__).resolve())+' --restore')
    print('Live audio, image rendering and CAVA still need verification on your desktop.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,subprocess.TimeoutExpired) as error:raise SystemExit(str(error))
