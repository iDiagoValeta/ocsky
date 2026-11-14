# Using ocsky

## Keys

| Key | Action |
|---|---|
| `↑` `↓` or `j` `k` | Select a session |
| `PgUp` `PgDn` | Jump ten rows |
| `enter`, `l` or `→` | Open the trace of the selected session |
| `esc`, `h` or `←` | Go back |
| `tab` or `c` | Switch between the sky and the 24 hour clock |
| `n` | Next backdrop of the sky: stars, galaxy, aurora |
| `space` | Fold or unfold finished subagents |
| `a` | Show or hide finished sessions |
| `r` | Next time range: 1h, 6h, 24h, 7d |
| `o` | Open the session in opencode |
| `y` / `Y` | Copy the session id / the session directory |
| `L` | Next language |
| `t` | Switch between light and dark, within the same palette family |
| `p` | Palette menu: type to filter, `↑` `↓` to try one, `⏎` to keep it, `esc` to go back |
| `?` | Help |
| `q` or `ctrl-c` | Quit |

The copy keys use the terminal's OSC 52 escape sequence, so the terminal must allow clipboard writes.

## Options

| Option | Meaning |
|---|---|
| `--range {1h,6h,24h,7d}` | Time window of sessions to show (default `24h`) |
| `--all` | Start with the history visible |
| `--view {sky,clock,trace}` | View to start in |
| `--backdrop {stars,galaxy,aurora}` | What the sky draws behind the list (default: the last one used) |
| `--light` | Light palette (Catppuccin Latte, or the light side of the remembered palette) |
| `--palette NAME` | Colour palette, one of the names the menu lists in lower case with dashes, such as `rose-pine-dawn` (default: the last one used) |
| `--db PATH` | opencode database file |
| `--colors {truecolor,256}` | 24-bit colours or the 256-colour palette (default: by terminal) |
| `--once COLSxROWS` | Print one frame of that size and exit |
| `--lang {en,es}` | Interface language |
| `--demo` | Run on a generated demo database |
| `--version` | Print the version and exit |

## Database

The database defaults to `$XDG_DATA_HOME/opencode/opencode.db`, or `~/.local/share/opencode/opencode.db` when the variable is unset. On Windows, where opencode's location is not confirmed, ocsky tries `XDG_DATA_HOME`, `%LOCALAPPDATA%` and `%APPDATA%` in that order and takes the first that exists; use `--db` if it guesses wrong.

## Language and preferences

English by default. Use `--lang es` or the `L` key for Spanish. The language, the backdrop and the palette are remembered in `~/.config/ocsky/config.json` (`$XDG_CONFIG_HOME/ocsky/config.json` when set, `%APPDATA%\ocsky\config.json` on Windows).

## Platforms

| Platform | Status |
|---|---|
| Linux | Supported. Running opencode processes are read from `/proc`. |
| macOS | Supported. Processes are read with `ps` and `lsof`. |
| Windows | Experimental. There is no process detection, so the waiting state is not detected. Not yet verified on a real Windows machine. |

CI runs the test suite and the install smoke test on Linux, macOS and Windows.
