#!/usr/bin/env lua
-- Find and display the largest files on the filesystem with deletion suggestions.

-- ── categories ──────────────────────────────────────────────────────────────

local EXT_TO_CAT = {}
local function def(cat, ...)
  for _, e in ipairs({...}) do EXT_TO_CAT["." .. e] = cat end
end
def("Video",      "mp4","mkv","avi","mov","wmv","flv","webm","m4v","ts","vob")
def("Audio",      "mp3","flac","wav","aac","ogg","m4a","wma","opus")
def("Image",      "jpg","jpeg","png","gif","bmp","tiff","webp","heic","raw","cr2","nef")
def("Archive",    "zip","tar","gz","bz2","xz","7z","rar","zst","tgz","tbz2","tbz")
def("Disk Image", "iso","img","vmdk","vdi","qcow2","dmg")
def("Document",   "pdf","doc","docx","xls","xlsx","ppt","pptx","odt","ods")
def("Code",       "py","js","ts","go","rs","c","cpp","h","java","rb","sh")
def("Database",   "db","sqlite","sqlite3","sql")
def("Package",    "deb","rpm","pkg","apk","msi","exe")
def("Log",        "log")
def("Cache",      "cache")
def("Backup",     "bak","old","orig","backup")
def("Library",    "so","dylib","dll","a")

local DEL_PATHS = {
  "/.cache/","/tmp/","/var/tmp/","/var/cache/","/.local/share/Trash/",
  "/__pycache__/","/node_modules/","/.npm/_cacache/","/.cargo/registry/cache/",
  "/go/pkg/mod/cache/","/.gradle/caches/","/.m2/repository/",
  "/.thumbnails/","/thumbnails/",
}
local DEL_EXTS  = { [".log"]=true,[".bak"]=true,[".old"]=true,[".orig"]=true,
                    [".backup"]=true,[".cache"]=true,[".pyc"]=true,[".pyo"]=true }
local DEL_NAMES = { ["core"]=true,["core.gz"]=true,[".DS_Store"]=true,
                    ["Thumbs.db"]=true,["desktop.ini"]=true,
                    ["npm-debug.log"]=true,["yarn-error.log"]=true }

-- ── helpers ──────────────────────────────────────────────────────────────────

local function categorize(path, ext)
  local p = path:lower()
  if p:find("/node_modules/", 1, true) then return "Package" end
  if p:find("/__pycache__/",  1, true) or ext == ".pyc" then return "Cache" end
  if p:find("/.cache/", 1, true) or p:find("/cache/", 1, true) then return "Cache" end
  if p:find("/log/",  1, true) or p:find("/logs/", 1, true) then return "Log" end
  return EXT_TO_CAT[ext:lower()] or "Other"
end

local function is_deletable(path, ext, name)
  local p = path:lower()
  for _, pat in ipairs(DEL_PATHS) do
    if p:find(pat, 1, true) then
      return true, "in " .. pat:gsub("^/",""):gsub("/$","")
    end
  end
  if DEL_EXTS[ext:lower()]   then return true, ext .. " file"   end
  if DEL_NAMES[name:lower()] then return true, "temp/junk file" end
  return false, ""
end

local function human_size(n)
  for _, u in ipairs({"B","KB","MB","GB","TB"}) do
    if n < 1024 then return ("%.1f %s"):format(n, u) end
    n = n / 1024
  end
  return ("%.1f PB"):format(n)
end

local function shell_quote(s)
  return "'" .. s:gsub("'", "'\\''") .. "'"
end

local function term_width()
  local h = io.popen("tput cols 2>/dev/null")
  local w = h and tonumber(h:read("*l"))
  if h then h:close() end
  return math.min(w or 120, 160)
end

-- ── platform ─────────────────────────────────────────────────────────────────

local IS_LINUX = (function()
  local h = io.popen("uname -s 2>/dev/null")
  local s = h and h:read("*l") or ""
  if h then h:close() end
  return s == "Linux"
end)()

local function stat_cmd(root, xdev, min_size)
  if IS_LINUX then
    -- GNU stat: -c format, %d=dev %i=ino %s=size %n=name
    return ("find %s %s -type f -size +%dc -print0 2>/dev/null"
         .. " | xargs -0 stat -c '%%d %%i %%s %%n' 2>/dev/null"):format(
              shell_quote(root), xdev, min_size - 1)
  else
    -- BSD/macOS stat: -f format, %d=dev %i=ino %z=size %N=name
    return ("find %s %s -type f -size +%dc -print0 2>/dev/null"
         .. " | xargs -0 stat -f '%%d %%i %%z %%N' 2>/dev/null"):format(
              shell_quote(root), xdev, min_size - 1)
  end
end

-- ── scan ─────────────────────────────────────────────────────────────────────

local function scan(roots, skip_mounts, min_size)
  local seen    = {}
  local entries = {}

  for _, root in ipairs(roots) do
    local xdev = skip_mounts and "-xdev" or ""
    local cmd  = stat_cmd(root, xdev, min_size)

    local h = io.popen(cmd)
    if not h then
      io.stderr:write("error: cannot scan " .. root .. "\n")
    else
      for line in h:lines() do
        local dev, ino, sz, path = line:match("^(%d+) (%d+) (%d+) (.+)$")
        if dev then
          local key = dev .. ":" .. ino
          if not seen[key] then
            seen[key] = true
            local name = path:match("[^/]+$") or path
            local ext  = name:match("(%.[^.]+)$") or ""
            local cat  = categorize(path, ext)
            local del, reason = is_deletable(path, ext, name)
            entries[#entries + 1] = {
              path = path, size = tonumber(sz),
              category = cat, deletable = del, reason = reason,
            }
          end
        end
      end
      h:close()
    end
  end

  table.sort(entries, function(a, b) return a.size > b.size end)
  return entries
end

-- ── output ───────────────────────────────────────────────────────────────────

local function print_table(entries, top_n, color)
  -- only show files suggested for deletion
  local deletable = {}
  for _, e in ipairs(entries) do
    if e.deletable then deletable[#deletable + 1] = e end
  end
  local n = math.min(top_n, #deletable)
  if n == 0 then
    print("\nNo files suggested for deletion.")
    return deletable
  end

  local w = term_width()

  local RED   = color and "\27[31m"  or ""
  local CYAN  = color and "\27[36m"  or ""
  local BOLD  = color and "\27[1m"   or ""
  local DIM   = color and "\27[2m"   or ""
  local RST   = color and "\27[0m"   or ""

  local CW = { num=4, size=10, cat=12, reason=22 }
  -- row: "│ num │ size │ cat │ reason │ path │"
  local overhead = 2 + CW.num + 3 + CW.size + 3 + CW.cat + 3 + CW.reason + 3 + 2
  local path_w   = math.max(10, w - overhead)

  local H = "─"
  local function hline(l, junc, r)
    local segs = {
      H:rep(CW.num+2), H:rep(CW.size+2), H:rep(CW.cat+2),
      H:rep(CW.reason+2), H:rep(path_w+2),
    }
    return l .. table.concat(segs, junc) .. r
  end

  local row_fmt = "│ %4s │ %10s │ %-12s │ %-22s │ %-" .. path_w .. "s │"
  local function make_row(num, size, cat, reason, path)
    return row_fmt:format(num, size, cat, reason, path)
  end

  local function truncate(s, maxw)
    if #s <= maxw then return s end
    return "\xe2\x80\xa6" .. s:sub(-(maxw-1))  -- UTF-8 ellipsis …
  end

  print(("\n%s%sDeletion Candidates — Top %d by Size%s"):format(BOLD, CYAN, n, RST))
  print(DIM .. hline("╭", "┬", "╮") .. RST)
  print(BOLD .. make_row("#", "Size", "Category", "Reason", "Path") .. RST)
  print(DIM .. hline("├", "┼", "┤") .. RST)

  local total = 0
  for i = 1, n do
    local e = deletable[i]
    local r = make_row(i, human_size(e.size), e.category,
                       e.reason, truncate(e.path, path_w))
    print((color and RED or "") .. r .. (color and RST or ""))
    total = total + e.size
  end

  print(DIM .. hline("╰", "┴", "╯") .. RST)
  print(("  %sTotal reclaimable:%s %s%s (%d files)%s"):format(
        BOLD, RST, RED, human_size(total), n, RST))

  return deletable, n
end

local function print_commands(deletable, n, color)
  if not deletable or n == 0 then return end

  local BOLD  = color and "\27[1m"   or ""
  local CYAN  = color and "\27[36m"  or ""
  local DIM   = color and "\27[2m"   or ""
  local RST   = color and "\27[0m"   or ""

  print(("\n%s%sSuggested cleanup commands:%s"):format(BOLD, CYAN, RST))
  for i = 1, n do
    print("  rm -f " .. shell_quote(deletable[i].path))
  end
  print(DIM .. "\n  # or delete all at once:" .. RST)
  local paths = {}
  for i = 1, n do paths[i] = shell_quote(deletable[i].path) end
  print("  rm -f " .. table.concat(paths, " \\\n       "))
end

-- ── arg parsing ──────────────────────────────────────────────────────────────

local function parse_args()
  local opts = { roots={}, top=10, min_size=1024*1024, skip_mounts=true, plain=false, yolo=false }
  local i = 1
  while i <= #arg do
    local a = arg[i]
    if a == "-h" or a == "--help" then
      io.write(
        "usage: turbo-clean [opts] [roots...]\n"
        .. "  -n N, --top N     files to show (default: 10)\n"
        .. "  --min-size BYTES  minimum size in bytes (default: 1048576)\n"
        .. "  --no-skip-mounts  cross filesystem boundaries\n"
        .. "  --plain           disable ANSI color\n"
        .. "  --yolo            WARNING: immediately deletes all candidate files with no confirmation\n"
        .. "  roots             paths to scan (default: /)\n")
      os.exit(0)
    elseif a == "-n" or a == "--top" then
      i = i + 1; opts.top = tonumber(arg[i]) or opts.top
    elseif a:match("^%-n(%d+)$") then
      opts.top = tonumber(a:match("^%-n(%d+)$"))
    elseif a == "--min-size" then
      i = i + 1; opts.min_size = tonumber(arg[i]) or opts.min_size
    elseif a == "--no-skip-mounts" then
      opts.skip_mounts = false
    elseif a == "--plain" then
      opts.plain = true
    elseif a == "--yolo" then
      opts.yolo = true
    elseif not a:match("^%-") then
      opts.roots[#opts.roots + 1] = a
    else
      io.stderr:write("unknown option: " .. a .. "\n"); os.exit(1)
    end
    i = i + 1
  end
  if #opts.roots == 0 then opts.roots = {"/"} end
  return opts
end

-- ── main ─────────────────────────────────────────────────────────────────────

local opts  = parse_args()
local color = not opts.plain and os.execute("[ -t 1 ]") == true

io.stderr:write(("Scanning %s (min size: %s) ...\n"):format(
  table.concat(opts.roots, ", "), human_size(opts.min_size)))

local entries = scan(opts.roots, opts.skip_mounts, opts.min_size)

io.stderr:write(("Found %d files above threshold.\n"):format(#entries))

if #entries == 0 then
  print("No files found.")
  os.exit(0)
end

local deletable, shown = print_table(entries, opts.top, color)

if opts.yolo and deletable and shown and shown > 0 then
  local RED  = color and "\27[31m" or ""
  local BOLD = color and "\27[1m"  or ""
  local RST  = color and "\27[0m"  or ""
  io.stderr:write(("\n%s%sWARNING: --yolo active. Deleting %d files now...%s\n"):format(BOLD, RED, shown, RST))
  local paths = {}
  for i = 1, shown do paths[i] = shell_quote(deletable[i].path) end
  os.execute("rm -f " .. table.concat(paths, " "))
  io.stderr:write("Done.\n")
else
  print_commands(deletable, shown, color)
end
