<#
.SYNOPSIS
    Multi-engine parallel web search via Invoke-WebRequest.
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File search.ps1 "Claude Code"
    powershell -ExecutionPolicy Bypass -File search.ps1 "Vue3 教程" -Lang zh
    powershell -ExecutionPolicy Bypass -File search.ps1 "rust async" -Engines "bing,google" -Json
#>
param(
    [Parameter(Position=0, Mandatory=$true)]
    [string]$Query,
    [string]$Engines = "bing,google,duckduckgo,sogou",
    [int]$Limit = 10,
    [switch]$Json,
    [string]$Lang = "en",
    [string]$AllowedDomains = "",
    [string]$BlockedDomains = "",
    [int]$MaxRetries = 2,
    [int]$TimeoutSeconds = 15
)
$ErrorActionPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Invoke-UrlEncode([string]$T) { return [System.Uri]::EscapeDataString($T) }
function ConvertFrom-HtmlEntity([string]$T) {
    if ([string]::IsNullOrEmpty($T)) { return $T }
    $d = [System.Net.WebUtility]::HtmlDecode($T)
    $d = $d -replace '<[^>]+>', ''
    return $d.Trim()
}

function Invoke-WithRetry([scriptblock]$Action, [int]$MaxRetries = 2) {
    for ($i = 0; $i -lt $MaxRetries; $i++) {
        try {
            return & $Action
        } catch {
            if ($i -eq $MaxRetries - 1) { throw }
            Start-Sleep -Seconds (1 * ($i + 1))
        }
    }
}

function Test-DomainFilter([string]$Url, [string]$Allowed, [string]$Blocked) {
    if ([string]::IsNullOrEmpty($Allowed) -and [string]::IsNullOrEmpty($Blocked)) {
        return $true
    }
    
    # Simple string matching for domain filtering
    $urlLower = $Url.ToLower()
    
    # Check blocked domains first
    if (-not [string]::IsNullOrEmpty($Blocked)) {
        $blockedDomains = $Blocked -split '[,;]' | ForEach-Object { $_.Trim().ToLower() }
        foreach ($domain in $blockedDomains) {
            if ($urlLower -match "https?://([^/]*\.)?$([regex]::Escape($domain))") {
                return $false
            }
        }
    }
    
    # Check allowed domains
    if (-not [string]::IsNullOrEmpty($Allowed)) {
        $allowedDomains = $Allowed -split '[,;]' | ForEach-Object { $_.Trim().ToLower() }
        $isAllowed = $false
        foreach ($domain in $allowedDomains) {
            if ($urlLower -match "https?://([^/]*\.)?$([regex]::Escape($domain))") {
                $isAllowed = $true
                break
            }
        }
        return $isAllowed
    }
    
    return $true
}

$Q = Invoke-UrlEncode $Query
$SearchUrls = [ordered]@{
    bing="https://www.bing.com/search?q=$Q"; google="https://www.google.com/search?q=$Q"
    duckduckgo="https://html.duckduckgo.com/html/?q=$Q"; baidu="https://www.baidu.com/s?wd=$Q"
    sogou="https://www.sogou.com/web?query=$Q"
}

function Fetch-Html([string]$Url) {
    $retryAction = {
        $request = [System.Net.HttpWebRequest]::Create($Url)
        $request.UserAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        $request.Accept = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        $request.Headers.Add("Accept-Language", "en-US,en;q=0.9")
        $request.Timeout = $TimeoutSeconds * 1000
        $request.ReadWriteTimeout = $TimeoutSeconds * 1000
        
        try {
            $response = $request.GetResponse()
            $stream = $response.GetResponseStream()
            
            # Read all bytes into memory stream
            $memoryStream = New-Object System.IO.MemoryStream
            $buffer = New-Object byte[] 4096
            $bytesRead = 0
            do {
                $bytesRead = $stream.Read($buffer, 0, $buffer.Length)
                if ($bytesRead -gt 0) {
                    $memoryStream.Write($buffer, 0, $bytesRead)
                }
            } while ($bytesRead -gt 0)
            
            $bytes = $memoryStream.ToArray()
            $memoryStream.Close()
            $stream.Close()
            $response.Close()
            
            # Detect encoding
            $encoding = [System.Text.Encoding]::UTF8 # default
            
            # Check BOM
            if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
                $encoding = [System.Text.Encoding]::UTF8
            } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFF -and $bytes[1] -eq 0xFE) {
                $encoding = [System.Text.Encoding]::Unicode
            } elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 0xFE -and $bytes[1] -eq 0xFF) {
                $encoding = [System.Text.Encoding]::BigEndianUnicode
            } else {
                # Check Content-Type header
                $contentType = $response.ContentType
                if ($contentType -match "charset=([^;]+)") {
                    $charset = $matches[1].Trim().ToLower()
                    try {
                        $encoding = [System.Text.Encoding]::GetEncoding($charset)
                    } catch {
                        # Invalid charset, use default
                    }
                } else {
                    # Guess encoding based on domain
                    if ($Url -match "bing\.com|baidu\.com|sogou\.com") {
                        # Chinese search engines often use GBK
                        $encoding = [System.Text.Encoding]::GetEncoding("GBK")
                    }
                }
            }
            
            # Decode bytes
            return $encoding.GetString($bytes)
        } catch {
            throw $_
        }
    }
    
    try {
        return Invoke-WithRetry -Action $retryAction -MaxRetries $MaxRetries
    } catch {
        Write-Host "Warning: Failed to fetch $Url after $MaxRetries retries - $_" -ForegroundColor Yellow
        return $null
    }
}

function Parse-Bing([string]$H) {
    $r = @(); $flat = $H -replace "`r`n","" -replace "`n",""
    $ms = [regex]::Matches($flat, '<h2 class="">(.*?)</h2>\s*<div class="b_caption">(.*?)</div>')
    foreach ($m in $ms) {
        if ($r.Count -ge $Limit) { break }
        $block = $m.Value

        # Try base64 URL first (curl-style), then direct URL (PS-style)
        $url = $null
        $um = [regex]::Match($block, 'u=a1([A-Za-z0-9+/=_-]+)')
        if ($um.Success) {
            $b64 = $um.Groups[1].Value.Replace('-','+').Replace('_','/')
            $mod = $b64.Length % 4
            if ($mod -eq 2) { $b64 += "==" } elseif ($mod -eq 3) { $b64 += "=" }
            try { $url = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64)) } catch {}
        }
        if ([string]::IsNullOrEmpty($url)) {
            $hm = [regex]::Match($block, 'href="(https?://[^"]+)"')
            if ($hm.Success) { $url = $hm.Groups[1].Value }
        }
        if ([string]::IsNullOrEmpty($url)) { continue }
        if ($url -match 'bing\.com/search|microsoft\.com') { continue }

        $title = ConvertFrom-HtmlEntity ($m.Groups[1].Value -replace '<[^>]+>','')
        if ([string]::IsNullOrWhiteSpace($title)) { $title = ($url -replace 'https?://','' -replace '/.*','') }

        $snip = ""
        $sm = [regex]::Match($m.Groups[2].Value, 'b_lineclamp\d+"?>(.*?)</p>')
        if ($sm.Success) { $snip = ConvertFrom-HtmlEntity ($sm.Groups[1].Value -replace '<[^>]+>','') }

        $r += @{ title=$title; url=$url; snippet=$snip }
    }
    return $r
}

function Parse-Google([string]$H) {
    $r = @(); $flat = $H -replace "`r`n","" -replace "`n",""
    $ms = [regex]::Matches($flat, 'href="/url\?q=(https?://[^&"]+)&[^"]*"[^>]*>(.*?)</a>')
    $seen = @{}
    foreach ($m in $ms) {
        if ($r.Count -ge $Limit) { break }
        $url = [System.Web.HttpUtility]::UrlDecode($m.Groups[1].Value)
        if ($url -match 'google\.com/search|youtube\.com/results') { continue }
        $dk = $url -replace '\?.*','' -replace '#.*',''
        if ($seen.ContainsKey($dk)) { continue }; $seen[$dk]=$true
        $title = ConvertFrom-HtmlEntity ($m.Groups[2].Value -replace '<[^>]+>','')
        $r += @{ title=$title; url=$url; snippet="" }
    }
    return $r
}

function Parse-Ddg([string]$H) {
    $r = @(); $flat = $H -replace "`r`n","" -replace "`n",""
    $ms = [regex]::Matches($flat, 'class="result__a"[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>')
    foreach ($m in $ms) {
        if ($r.Count -ge $Limit) { break }
        $url = $m.Groups[1].Value
        if ($url -match 'duckduckgo\.com') { continue }
        $title = ConvertFrom-HtmlEntity ($m.Groups[2].Value -replace '<[^>]+>','')
        $r += @{ title=$title; url=$url; snippet="" }
    }
    return $r
}

function Parse-Baidu([string]$H) {
    $r = @(); $flat = $H -replace "`r`n","" -replace "`n",""
    $ms = [regex]::Matches($flat, '<h3[^>]*class="t"[^>]*>\s*<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>')
    foreach ($m in $ms) {
        if ($r.Count -ge $Limit) { break }
        $title = ConvertFrom-HtmlEntity ($m.Groups[2].Value -replace '<[^>]+>','')
        $r += @{ title=$title; url=$m.Groups[1].Value; snippet="" }
    }
    return $r
}

function Parse-Sogou([string]$H) {
    $r = @(); $flat = $H -replace "`r`n","" -replace "`n",""
    # Sogou: <h3 class="vr-title">...<a href="/link?url=...">title</a>...</h3>
    $ms = [regex]::Matches($flat, '<h3 class="vr-title.*?</h3>')
    foreach ($m in $ms) {
        if ($r.Count -ge $Limit) { break }
        $block = $m.Value
        # Skip ads (blocks without <a> tag)
        if ($block -notmatch '<a ') { continue }
        # Extract href
        $hm = [regex]::Match($block, 'href="([^"]+)"')
        if (!$hm.Success) { continue }
        $url = $hm.Groups[1].Value
        # Convert relative /link?url= to absolute
        if ($url.StartsWith("/link")) { $url = "https://www.sogou.com$url" }
        # Extract title: text inside <a>, strip tags and HTML comments
        $title = ConvertFrom-HtmlEntity ($block -replace '.*<a[^>]*>' -replace '</a>.*' -replace '<[^>]+>','' -replace '<!--.*?-->','')
        $title = $title.Trim()
        if ([string]::IsNullOrWhiteSpace($title)) { continue }
        $r += @{ title=$title; url=$url; snippet="" }
    }
    return $r
}

function Fetch-Engine([string]$eng) {
    $url = $SearchUrls[$eng]
    if (!$url) { return @() }
    $html = Fetch-Html $url
    if ([string]::IsNullOrEmpty($html)) { return @() }
    $res = switch ($eng) {
        "bing"       { Parse-Bing $html }
        "google"     { Parse-Google $html }
        "duckduckgo" { Parse-Ddg $html }
        "baidu"      { Parse-Baidu $html }
        "sogou"      { Parse-Sogou $html }
        default      { @() }
    }
    return $res
}

# Normalize engines
if ($Engines -is [array]) { $el = $Engines | % { $_.ToString().Trim().ToLower() } }
else { $el = $Engines.ToString() -split '[,\s]+' | % { $_.Trim().ToLower() } | ? { $_ -ne '' } }
if ($Lang -eq "zh" -and $el -notcontains "baidu") { $el += "baidu" }
$ve = @()
foreach ($e in $el) { if ($SearchUrls.Contains($e)) { $ve += $e } else { Write-Host "Warning: Unknown engine '$e'" -ForegroundColor Yellow } }
if ($ve.Count -eq 0) { Write-Host "Error: No valid engines." -ForegroundColor Red; exit 1 }

$all = @(); $seen = @{}
foreach ($eng in $ve) {
    foreach ($r in (Fetch-Engine $eng)) {
        $url = $r.url
        if ([string]::IsNullOrWhiteSpace($url)) { continue }
        
        # Validate URL format
        if ($url -notmatch '^https?://') { continue }
        
        # Apply domain filtering
        if (-not (Test-DomainFilter -Url $url -Allowed $AllowedDomains -Blocked $BlockedDomains)) { continue }
        
        try { $uri = [System.Uri]$url; $dk = $uri.Host + $uri.AbsolutePath } catch { $dk = $url }
        if ($seen.ContainsKey($dk)) { continue }; $seen[$dk] = $true
        $all += [PSCustomObject]@{ Title=$r.title; Url=$r.url; Snippet=$r.snippet }
    }
}

if ($Json) {
    $all | ConvertTo-Json -Depth 3
} else {
    Write-Host ""; Write-Host "=== Search Results: `"$Query`" ===" -ForegroundColor Cyan
    Write-Host "Found $($all.Count) results from: $($ve -join ', ')" -ForegroundColor DarkGray; Write-Host ""
    $n = 1
    foreach ($r in $all) {
        Write-Host "$n. $($r.Title)" -ForegroundColor White
        Write-Host "   $($r.Url)" -ForegroundColor DarkCyan
        if (![string]::IsNullOrWhiteSpace($r.Snippet)) { Write-Host "   $($r.Snippet)" -ForegroundColor Gray }
        Write-Host ""; $n++
    }
}
