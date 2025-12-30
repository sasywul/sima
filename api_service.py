import requests
import re
from config import BASE_URL, PROXIES, HEADERS_ANDROID, HEADERS_BROWSER

# ==========================================
# 1. HELPER FORMATTER (DARI CODE MANTAP)
# ==========================================
def safe_json(resp):
    try: return resp.json()
    except: return None

def akademik_label(kode: str) -> str:
    if not kode: return ""
    kode = str(kode)
    if len(kode) < 5: return f"Semester {kode}"
    
    tahun = kode[:4]
    tipe = kode[-1]
    
    try:
        tahun_ajaran = f"{tahun}/{int(tahun)+1}"
        if tipe == "1": return f"{tahun_ajaran} Gasal"
        if tipe == "2": return f"{tahun_ajaran} Genap"
        if tipe == "3": return f"{tahun_ajaran} Antara"
    except: pass
    return f"Semester {kode}"

def format_nilai_text(nilai_data):
    # Logika Format Nilai ASLI dari codingan Anda (JSON Base)
    if not nilai_data: return "❌ Gagal memuat data (Server Error)."
    result = nilai_data.get("result", {})
    if not result: return "ℹ️ *Data Nilai Kosong*."
    
    nilai_list = result.get("nilai", [])
    if not nilai_list: return "ℹ️ *Belum ada Nilai Masuk*."

    text = "📘 *DAFTAR NILAI*\n"
    last_header = None
    
    sem_list = [n for n in nilai_list if n.get("list_semester")]

    if not sem_list: return "ℹ️ *Tidak ada data Semester Akademik.*"

    for n in sem_list:
        header = akademik_label(n.get("list_semester"))
        if header != last_header:
            text += f"\n📚 *{header}*\n"
            last_header = header
        
        mk = n.get('nama_makul', '-')
        sks = n.get('sks', '0')
        raw_val = n.get('n_huruf')
        bpm_status = str(n.get('bpm'))
        
        # Logika Status BPM
        if bpm_status == "0":
            val = "⚠️ Belum Input BPM"
        elif raw_val is None or raw_val == "":
            val = "Belum ada"
        else:
            val = raw_val
        
        text += f"• {mk} ({sks}) → *{val}*\n"

    return text.strip()

# ==========================================
# 2. PRESENSI (API) - CLEAN UX
# ==========================================
def api_login_android(nim, password):
    try:
        r = requests.patch(
            f"{BASE_URL}/login/sia",
            json={"username": nim, "password": password},
            headers=HEADERS_ANDROID,
            timeout=15, proxies=PROXIES
        )
        data = r.json()
        if data.get("result", {}).get("st") == "1":
            return data["result"]
    except: pass
    return None

def api_get_biodata(token):
    try:
        r = requests.put(
            f"{BASE_URL}/mhs/biodata",
            headers={"Authorization": token, **HEADERS_ANDROID},
            timeout=15, proxies=PROXIES
        )
        return r.json().get("result", {}).get("get_mhs", {}).get("kode_khusus")
    except: return None

def api_get_jadwal(token, kode_khusus):
    try:
        r = requests.put(
            f"{BASE_URL}/presensi/hari_ini/get",
            headers={"Authorization": token, **HEADERS_ANDROID},
            json={"kode_khusus": kode_khusus},
            timeout=15, proxies=PROXIES
        )
        return r.json().get("result", [])
    except: return []

def api_execute_presensi(token, kode_khusus, id_presensi):
    try:
        # 1. Log IP
        ip_resp = requests.get("https://api64.ipify.org/?format=json", timeout=5, proxies=PROXIES)
        my_ip = ip_resp.json().get("ip", "127.0.0.1")
        
        requests.patch(
            f"{BASE_URL}/presensi/hari_ini/log",
            headers={"Authorization": token, **HEADERS_ANDROID},
            json={
                "ip": my_ip,
                "keterangan": "Android 23049PCD8G (OS 15)", 
                "kode_khusus": kode_khusus
            },
            timeout=10, proxies=PROXIES
        )

        # 2. Press
        r = requests.patch(
            f"{BASE_URL}/presensi/hari_ini/press",
            json={"id_presensi": id_presensi, "kode_khusus": kode_khusus},
            headers={"Authorization": token, **HEADERS_ANDROID},
            timeout=20, proxies=PROXIES
        )
        return r.json()
    except Exception as e: return {"status": "500", "message": str(e)}

# ==========================================
# 3. REKAP ABSENSI (HITUNG SENDIRI)
# ==========================================
def hitung_presensi(pertemuan):
    total = hadir = alfa = 0
    for p in pertemuan:
        if p.get("st") != "1": continue
        if p.get("id_dosen") is None: continue

        total += 1
        # Asalkan st_presensi TIDAK None, dianggap HADIR
        if p.get("st_presensi") is not None:
            hadir += 1
        else:
            alfa += 1

    persen = round((hadir / total) * 100, 2) if total else 0
    return total, hadir, alfa, persen

def fetch_rekap_api(nim, password):
    session = requests.Session()
    if PROXIES: session.proxies.update(PROXIES)
    
    try:
        # Login
        r = session.patch(f"{BASE_URL}/login/sia", json={"username": nim, "password": password}, headers=HEADERS_ANDROID, timeout=20)
        data = safe_json(r)
        if not data or data.get("result", {}).get("st") != "1": 
            return "❌ *Login Gagal!* Cek NIM/Password."
        
        token = data["result"]["token"]
        auth_head = {"Authorization": token, **HEADERS_ANDROID}

        # Get Data Mhs & Jadwal
        r_bio = session.put(f"{BASE_URL}/mhs/biodata", headers=auth_head, timeout=20)
        kode_khusus = r_bio.json()["result"]["get_mhs"]["kode_khusus"]

        r_jadwal = session.put(f"{BASE_URL}/jadwal/get_jadwal", json={"kode_khusus": kode_khusus}, headers=auth_head, timeout=20)
        data_jadwal = safe_json(r_jadwal)
        
        semester_name = data_jadwal["result"]["semester_aktif"]["nama_semester"]
        jadwal_list = data_jadwal["result"]["jadwal"]

        output = f"📋 *REKAP PRESENSI: {semester_name}*\n\n"
        
        # Loop Detail
        for j in jadwal_list:
            r_det = session.put(
                f"{BASE_URL}/jadwal/detail_jadwal",
                json={"kode_khusus": kode_khusus, "id_jadwal": str(j["id_jadwal"])},
                headers=auth_head, timeout=20
            )
            data_det = safe_json(r_det)
            if not data_det: continue

            # Hitung
            pertemuan = data_det["result"]["pertemuan"]
            total, hadir, alfa, persen = hitung_presensi(pertemuan)

            icon = "✅" if persen >= 75 else "⚠️"
            if total == 0:
                output += f"📘 {j['nm_makul']}\n   _(Belum ada pertemuan)_\n\n"
            else:
                output += (
                    f"📘 *{j['nm_makul']}* ({j['sks']} SKS)\n"
                    f"   Hadir: {hadir} | Alfa: {alfa}\n"
                    f"   {icon} Total: *{persen}%* ({hadir}/{total})\n\n"
                )
        return output.strip()
    except Exception as e: return f"❌ Error Rekap: {e}"

# ==========================================
# 4. NILAI (API)
# ==========================================
def fetch_nilai_api(nim, password):
    session = requests.Session()
    if PROXIES: session.proxies.update(PROXIES)
    try:
        r = session.patch(f"{BASE_URL}/login/sia", json={"username": nim, "password": password}, headers=HEADERS_ANDROID, timeout=20)
        data = safe_json(r)
        if not data or data.get("result", {}).get("st") != "1": 
            return "❌ *Login Gagal!* NIM atau Password salah."
        
        token = data["result"]["token"]
        r_nilai = session.put(f"{BASE_URL}/his_pend/nilai", headers={"Authorization": token, **HEADERS_ANDROID}, timeout=30)
        return format_nilai_text(safe_json(r_nilai))
    except Exception as e: return f"❌ Error API: {e}"

# ==========================================
# 5. AUTO KHS (WEB SCRAPING - LOGIKA MANTAP)
# ==========================================
def get_web_session(nim, password):
    print(f"🔐 Login Web untuk NIM {nim}...")
    session = requests.Session()
    if PROXIES: session.proxies.update(PROXIES)

    try:
        r_home = session.get("https://sima.usm.ac.id/", headers=HEADERS_BROWSER, timeout=20)
        match = re.search(r'name=["\']token["\'][^>]*value=["\']([^"\']+)["\']', r_home.text)
        if not match: match = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']token["\']', r_home.text)
        if not match: return None
        
        payload = {"username": nim, "token": match.group(1), "password": password}
        headers_login = HEADERS_BROWSER.copy()
        headers_login["Referer"] = "https://sima.usm.ac.id/"
        
        r_login = session.post("https://sima.usm.ac.id/login", data=payload, headers=headers_login, timeout=20)
        
        if "Username atau Password Salah" in r_login.text or "Login Gagal" in r_login.text:
            return "WRONG_PASS"
        if 'dudoks_session' in session.cookies.get_dict():
            return session
        return None
    except Exception as e: return None

def scan_and_solve_khs(session):
    results = []
    # 1. SETUP ROUTE
    try:
        session.post("https://sima.usm.ac.id/app/routes", data={"id_aplikasi": "05494017904153", "level_key": "6f1e80f8-4fb3-11ea-9ef2-1cb72c27dd68", "id_bidang": "1"}, headers=HEADERS_BROWSER, timeout=10)
    except: return "❌ Gagal koneksi (Route Setup)."

    # 2. BUKA DAFTAR SEMESTER
    try:
        r_list = session.get("https://sima.usm.ac.id/histori_pendidikan/khs", headers=HEADERS_BROWSER, timeout=20)
        
        # Deteksi Cekal Keuangan
        if "kekurangan administrasi" in r_list.text or "lunas satu semester" in r_list.text:
            return "🚫 *AKSES DITOLAK KEUANGAN*\nBot mendeteksi peringatan: 'Masih ada kekurangan administrasi/UKT'."

        detail_links = re.findall(r'href=["\']([^"\']*/histori_pendidikan/khs/detail/[^"\']+)["\']', r_list.text)
        if not detail_links:
            if "Login" in r_list.text: return "❌ Sesi login terputus."
            return "✅ *Aman!* Tidak ada KHS/BPM yang perlu diisi."

        print(f"📄 Memproses {len(detail_links)} Semester...")
        processed_any = False
        
        # 3. LOOP DETAIL
        for idx, link_detail in enumerate(detail_links):
            full_url = link_detail if link_detail.startswith("http") else f"https://sima.usm.ac.id{link_detail}"
            try: r_detail = session.get(full_url, headers=HEADERS_BROWSER, timeout=20)
            except: continue
            
            # Cari Form BPM
            forms = re.findall(r'(<form[^>]*action="[^"]*input_bpm_khs"[^>]*>.*?</form>)', r_detail.text, re.DOTALL | re.IGNORECASE)
            if not forms: continue
            
            processed_any = True
            results.append(f"⚠️ Semester {idx+1}: Mengisi {len(forms)} Kuesioner...")
            
            # 4. ISI KUESIONER (LOGIKA MANTAP)
            url_save = "https://sima.usm.ac.id/histori_pendidikan/khs/save_bpm_khs"
            
            for i, form_html in enumerate(forms):
                # Helper Regex Bolak-Balik (Name/Value)
                def get_val(name):
                    pat = fr'name=["\']{name}["\'][^>]*value=["\']([^"\']+)["\']|value=["\']([^"\']+)["\'][^>]*name=["\']{name}["\']'
                    m = re.search(pat, form_html, re.IGNORECASE)
                    if m: return m.group(1) or m.group(2)
                    return None

                val_id_sem = get_val('id_semester')
                val_id_jad = get_val('id_jadwal')
                val_kd_khs = get_val('kode_khusus')
                val_id_prd = get_val('id_prodi')
                
                if val_id_sem and val_id_jad and val_kd_khs and val_id_prd:
                    # Payload List of Tuples (Cara Paling Benar)
                    payload_data = []
                    for q in range(1, 27):
                        payload_data.append(('id_semester', val_id_sem))
                        payload_data.append(('id_jadwal', val_id_jad))
                        payload_data.append(('kode_khusus', val_kd_khs))
                        payload_data.append(('id_prodi', val_id_prd))
                        payload_data.append(('id_ques[]', str(q)))
                        payload_data.append((f'skor[{q}]', '2'))

                    headers_post = HEADERS_BROWSER.copy()
                    headers_post["Referer"] = full_url 
                    headers_post["Content-Type"] = "application/x-www-form-urlencoded"
                    
                    try:
                        r_post = session.post(url_save, headers=headers_post, data=payload_data, timeout=15)
                        if r_post.status_code not in [200, 302]:
                            results.append(f"   ❌ Gagal Matkul ke-{i+1}")
                    except: pass
        
        if not processed_any: return "✅ *Aman!* Semua BPM KHS sudah terisi."
            
    except Exception as e: return f"❌ Error Scanning: {e}"
    
    if not results: return "✅ Proses Selesai. BPM terisi."
    return "\n".join(results) + "\n\n✅ *Selesai!* Coba cek /nilai sekarang."