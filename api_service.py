import requests
import re
from config import BASE_URL, PROXIES, HEADERS_ANDROID, HEADERS_BROWSER
from bs4 import BeautifulSoup

# ==========================================
# 1. HELPER FORMATTER & CHECKER (HUMANIS)
# ==========================================
def safe_json(resp):
    try: return resp.json()
    except: return None

def cek_status_code(response):
    """Helper deteksi error dengan bahasa yang ramah"""
    code = response.status_code
    if code == 403:
        return True, "🛡️ **Koneksi Terhalang**\nSistem kampus menolak akses bot (IP Block). Coba ganti jaringan atau matikan VPN ya."
    if code == 404:
        return True, "❓ **Data Tidak Ditemukan**\nAlamat API kampus sepertinya berubah."
    if code >= 500:
        return True, f"🤯 **Server Sedang Sibuk**\nSistem kampus lagi down ({code}). Coba beberapa saat lagi ya!"
    if code != 200:
        return True, f"⚠️ **Gangguan Koneksi**\nTerjadi kesalahan jaringan ({code})."
    return False, None

def akademik_label(kode: str) -> str:
    if not kode: return ""
    kode = str(kode)
    if len(kode) < 5: return f"Semester {kode}"
    try:
        tahun = kode[:4]
        tipe = kode[-1]
        tahun_ajaran = f"{tahun}/{int(tahun)+1}"
        if tipe == "1": return f"{tahun_ajaran} Gasal"
        if tipe == "2": return f"{tahun_ajaran} Genap"
        if tipe == "3": return f"{tahun_ajaran} Antara"
    except: pass
    return f"Semester {kode}"

def format_nilai_text(nilai_data):
    if not nilai_data: return "🥺 **Gagal Memuat Data**\nFormat data dari server tidak dikenali."
    result = nilai_data.get("result", {})
    if not result: return "📭 **Data Masih Kosong**\nBelum ada data nilai yang masuk."
    
    nilai_list = result.get("nilai", [])
    if not nilai_list: return "📭 **Belum Ada Nilai**\nTranskrip nilai kamu masih kosong."

    text = "🎓 **TRANSKRIP NILAI**\n"
    last_header = None
    sem_list = [n for n in nilai_list if n.get("list_semester")]

    if not sem_list: return "ℹ️ *Tidak ada data Semester Akademik.*"

    for n in sem_list:
        header = akademik_label(n.get("list_semester"))
        if header != last_header:
            text += f"\n📂 *{header}*\n"
            last_header = header
        
        mk = n.get('nama_makul', '-')
        sks = n.get('sks', '0')
        raw_val = n.get('n_huruf')
        bpm_status = str(n.get('bpm'))
        
        val = "⚠️ Belum Input BPM" if bpm_status == "0" else (raw_val if raw_val else "Belum Ada ")
        text += f"• {mk} ({sks}) → *{val}*\n"

    return text.strip()

# ==========================================
# 2. PRESENSI & JADWAL (API)
# ==========================================
def api_login_android(nim, password):
    try:
        try:
            r = requests.patch(f"{BASE_URL}/login/sia", json={"username": nim, "password": password}, headers=HEADERS_ANDROID, timeout=15, proxies=PROXIES)
        except requests.exceptions.ConnectionError:
            return "📡 **Gagal Terhubung**\nBot tidak bisa menghubungi server kampus. Cek koneksi internetmu ya."

        if r.status_code == 403: return "🛡️ **Akses Dibatasi**\nFirewall kampus memblokir koneksi ini."
        
        data = safe_json(r)
        if not data: return "😵 **Respon Server Aneh**\nServer tidak mengirim data yang valid."

        if data.get("result", {}).get("st") == "1":
            return data["result"]
        else:
            msg = data.get("result", {}).get("msg", "Cek lagi ya.")
            return f"🔑 **Gagal Masuk**\nSepertinya NIM atau Password salah ketik. Coba dicek lagi ya!\n\n_(Info Server: {msg})_"
    except Exception as e: return f"🐛 **Error Sistem:** {e}"

def api_get_biodata(token):
    try:
        r = requests.put(f"{BASE_URL}/mhs/biodata", headers={"Authorization": token, **HEADERS_ANDROID}, timeout=15, proxies=PROXIES)
        return r.json().get("result", {}).get("get_mhs", {}).get("kode_khusus")
    except: return None

def api_get_jadwal(token, kode_khusus):
    try:
        r = requests.put(f"{BASE_URL}/presensi/hari_ini/get", headers={"Authorization": token, **HEADERS_ANDROID}, json={"kode_khusus": kode_khusus}, timeout=15, proxies=PROXIES)
        return r.json().get("result", [])
    except: return []

def api_execute_presensi(token, kode_khusus, id_presensi):
    try:
        my_ip = "127.0.0.1"
        try:
            ip_r = requests.get("https://api64.ipify.org?format=json", timeout=3, proxies=PROXIES)
            if ip_r.status_code == 200: my_ip = ip_r.json()['ip']
        except: pass

        r_log = requests.patch(
            f"{BASE_URL}/presensi/hari_ini/log",
            headers={"Authorization": token, **HEADERS_ANDROID},
            json={"ip": my_ip, "keterangan": "Android 23049PCD8G (OS 15)", "kode_khusus": kode_khusus},
            timeout=10, proxies=PROXIES
        )
        is_err, msg_err = cek_status_code(r_log)
        if is_err: return {"status": "error", "message": msg_err}

        r = requests.patch(
            f"{BASE_URL}/presensi/hari_ini/press",
            json={"id_presensi": id_presensi, "kode_khusus": kode_khusus},
            headers={"Authorization": token, **HEADERS_ANDROID},
            timeout=20, proxies=PROXIES
        )
        is_err, msg_err = cek_status_code(r)
        if is_err: return {"status": "error", "message": msg_err}
        
        return r.json()
    except Exception as e: return {"status": "error", "message": str(e)}

# ==========================================
# 3. NILAI & REKAP (API)
# ==========================================
def fetch_nilai_api(nim, password):
    session = requests.Session()
    if PROXIES: session.proxies.update(PROXIES)
    try:
        try: r = session.patch(f"{BASE_URL}/login/sia", json={"username": nim, "password": password}, headers=HEADERS_ANDROID, timeout=20)
        except: return "📡 **Koneksi Terputus**."

        is_err, msg_err = cek_status_code(r)
        if is_err: return msg_err

        data = safe_json(r)
        if not data or data.get("result", {}).get("st") != "1": 
             pesan_server = data.get("result", {}).get("msg", "Unknown")
             return f"🔑 **Gagal Masuk**\nNIM atau Password mungkin salah. Coba periksa kembali.\n_(Server: {pesan_server})_"
        
        token = data["result"]["token"]
        r_nilai = session.put(f"{BASE_URL}/his_pend/nilai", headers={"Authorization": token, **HEADERS_ANDROID}, timeout=30)
        
        is_err, msg_err = cek_status_code(r_nilai)
        if is_err: return msg_err

        return format_nilai_text(safe_json(r_nilai))
    except Exception as e: return f"🐛 **Error:** {e}"

def fetch_rekap_api(nim, password):
    session = requests.Session()
    if PROXIES: session.proxies.update(PROXIES)
    try:
        try: r = session.patch(f"{BASE_URL}/login/sia", json={"username": nim, "password": password}, headers=HEADERS_ANDROID, timeout=20)
        except: return "📡 **Koneksi Terputus**."

        is_err, msg_err = cek_status_code(r)
        if is_err: return msg_err

        data = safe_json(r)
        if not data or data.get("result", {}).get("st") != "1": return "🔑 **Gagal Masuk**\nCek NIM/Password ya."
        
        token = data["result"]["token"]
        auth_head = {"Authorization": token, **HEADERS_ANDROID}

        r_bio = session.put(f"{BASE_URL}/mhs/biodata", headers=auth_head, timeout=20)
        if r_bio.status_code != 200: return "⛔ Gagal ambil biodata."
        kode_khusus = r_bio.json()["result"]["get_mhs"]["kode_khusus"]
        
        r_jadwal = session.put(f"{BASE_URL}/jadwal/get_jadwal", json={"kode_khusus": kode_khusus}, headers=auth_head, timeout=20)
        data_jadwal = safe_json(r_jadwal)
        
        if not data_jadwal: return "📭 **Jadwal Kosong**\nTidak ada data jadwal untuk direkap."
        
        semester_name = data_jadwal["result"]["semester_aktif"]["nama_semester"]
        jadwal_list = data_jadwal["result"]["jadwal"]

        output = f"📊 **REKAP PRESENSI: {semester_name}**\n\n"
        for j in jadwal_list:
            r_det = session.put(f"{BASE_URL}/jadwal/detail_jadwal", json={"kode_khusus": kode_khusus, "id_jadwal": str(j["id_jadwal"])}, headers=auth_head, timeout=20)
            if r_det.status_code != 200: continue
            
            data_det = safe_json(r_det)
            if not data_det: continue

            pertemuan = data_det["result"]["pertemuan"]
            total = hadir = alfa = 0
            for p in pertemuan:
                if p.get("st") != "1" or p.get("id_dosen") is None: continue
                total += 1
                if p.get("st_presensi") is not None: hadir += 1
                else: alfa += 1

            persen = round((hadir / total) * 100, 2) if total else 0
            icon = "✅" if persen >= 75 else "⚠️"
            if total > 0:
                output += (f"📘 *{j['nm_makul']}*\n   Hadir: {hadir} | Alfa: {alfa}\n   {icon} Total: *{persen}%* ({hadir}/{total})\n\n")
            else:
                output += f"📘 {j['nm_makul']}\n   _(Belum ada pertemuan)_\n\n"

        return output.strip()
    except Exception as e: return f"🐛 Error Rekap: {e}"

# ==========================================
# 4. WEB SESSION (LOGIN SCRAPING)
# ==========================================
def get_web_session(nim, password):
    print(f"🔐 [WEB] Login NIM {nim}...")
    session = requests.Session()
    if PROXIES: session.proxies.update(PROXIES)
    session.headers.update(HEADERS_BROWSER)

    try:
        try: r_home = session.get("https://sima.usm.ac.id/", timeout=15)
        except requests.exceptions.ConnectionError: return "📡 **Koneksi Web Bermasalah**\nTidak bisa membuka web SIMA."
        except requests.exceptions.Timeout: return "⌛ **Koneksi Timeout**"
        
        if r_home.status_code == 403: return "🛡️ **Akses Web Terhalang**\nFirewall kampus memblokir bot."

        match = re.search(r'name=["\']token["\'][^>]*value=["\']([^"\']+)["\']', r_home.text)
        if not match: match = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']token["\']', r_home.text)
        if not match: return "⚙️ **Gagal Membaca Token**\nWeb kampus mungkin sedang update."
        
        payload = {"username": nim, "token": match.group(1), "password": password}
        headers_login = HEADERS_BROWSER.copy()
        headers_login["Referer"] = "https://sima.usm.ac.id/"
        
        r_login = session.post("https://sima.usm.ac.id/login", data=payload, headers=headers_login, timeout=20)
        
        if r_login.status_code == 403: return "🛡️ **Login Web Ditolak** (403)"
        if "Username atau Password Salah" in r_login.text or "Login Gagal" in r_login.text: 
            return "🔑 **Gagal Masuk Web**\nPassword atau NIM salah."
        if 'dudoks_session' in session.cookies.get_dict(): return session
            
        return "❌ **Gagal Login Web** (Sesi tidak terbentuk)."
    except Exception as e: return f"🐛 Error Web: {e}"

# ==========================================
# 5. SKPI & AUTO KHS (SCRAPING)
# ==========================================
def fetch_skpi_web(nim, password):
    session_or_error = get_web_session(nim, password)
    if isinstance(session_or_error, str): return session_or_error
    session = session_or_error

    try:
        r_route = session.post("https://sima.usm.ac.id/app/routes", data={"id_aplikasi": "99806946277720066", "level_key": "f6f9ab8e-ec73-11ec-8326-56cb879f2d55", "id_bidang": "1"}, timeout=15)
        if r_route.status_code == 403: return "🛡️ **Akses SKPI Terhalang**"

        url_target = "https://apps.usm.ac.id/skpi/mahasiswa/daftar_kegiatan"
        r = session.get(url_target, timeout=20)
        
        if r.status_code == 403: return "🛡️ **Halaman SKPI Diblokir**"
        if "login" in r.url.lower(): return "⌛ **Sesi Habis**\nSilakan coba lagi."

        soup = BeautifulSoup(r.text, "html.parser")
        target_table = None
        tab_2 = soup.find("div", {"id": "tab_2"})
        if tab_2: target_table = tab_2.find("table")
        if not target_table:
            for tbl in soup.find_all("table"):
                if "Bobot SKP" in tbl.get_text(): target_table = tbl; break
        
        if not target_table: return "📭 **Data SKPI Masih Kosong**"

        data = []; current_cat = "Lainnya"; total_skp = 0
        rows = target_table.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if not cols: continue
            txt = cols[0].get_text(strip=True).lower()
            if "jumlah skp" in txt or "total nilai" in txt: continue
            if len(cols) == 1 or (cols[0].has_attr("colspan") and len(cols) < 4):
                if cols[0].get_text(strip=True): current_cat = cols[0].get_text(strip=True)
                continue
            if len(cols) >= 4:
                nama = cols[1].get_text(strip=True)
                peran = cols[2].get_text(strip=True)
                skp_str = cols[3].get_text(strip=True)
                if not nama or nama == "-" or nama.isdigit() or "nama kegiatan" in nama.lower(): continue
                try: val = int(skp_str)
                except: val = 0
                total_skp += val
                data.append({"cat": current_cat, "nama": nama, "peran": peran, "skp": val})

        if not data: return f"📊 Total SKP: {total_skp}"
        
        res = "📜 **DAFTAR KEGIATAN SKPI**\n\n"; last_cat = None
        for d in data:
            if d['cat'] != last_cat: res += f"🏷️ *{d['cat']}*\n"; last_cat = d['cat']
            res += f"• {d['nama']}\n   ├ Sbg: {d['peran']}\n   └ Bobot: {d['skp']} SKP\n\n"
        res += f"📊 *Total SKP*: {total_skp}"
        return res.strip()
    except Exception as e: return f"🐛 Error Parsing: {e}"

def scan_and_solve_khs(session_or_error):
    if isinstance(session_or_error, str): return session_or_error
    session = session_or_error
    results = []
    try:
        r_route = session.post("https://sima.usm.ac.id/app/routes", data={"id_aplikasi": "05494017904153", "level_key": "6f1e80f8-4fb3-11ea-9ef2-1cb72c27dd68", "id_bidang": "1"}, timeout=10)
        if r_route.status_code == 403: return "🛡️ **Akses KHS Terhalang**"

        r_list = session.get("https://sima.usm.ac.id/histori_pendidikan/khs", timeout=20)
        if r_list.status_code == 403: return "🛡️ **Halaman KHS Terhalang**"

        # --- GANTI PESAN KEUANGAN JADI LEBIH SOPAN ---
        if "kekurangan administrasi" in r_list.text or "lunas satu semester" in r_list.text:
            return "💸 **Info Administrasi**\nMaaf, bot mendeteksi ada tagihan/administrasi yang belum diselesaikan di sistem kampus.\n\n_Silakan cek bagian keuangan ya._"

        detail_links = re.findall(r'href=["\']([^"\']*/histori_pendidikan/khs/detail/[^"\']+)["\']', r_list.text)
        if not detail_links:
            if "Login" in r_list.text: return "⌛ **Sesi Habis**"
            return "✅ **Aman!**\nTidak ada Kuesioner/BPM yang perlu diisi saat ini."

        processed_any = False
        for idx, link_detail in enumerate(detail_links):
            full_url = link_detail if link_detail.startswith("http") else f"https://sima.usm.ac.id{link_detail}"
            try: r_detail = session.get(full_url, timeout=20)
            except: continue
            
            if r_detail.status_code == 403: results.append(f"🛡️ Semester {idx+1} Blocked"); continue

            forms = re.findall(r'(<form[^>]*action="[^"]*input_bpm_khs"[^>]*>.*?</form>)', r_detail.text, re.DOTALL | re.IGNORECASE)
            if not forms: continue
            
            processed_any = True
            results.append(f"📝 Semester {idx+1}: Mengisi {len(forms)} Matkul...")
            url_save = "https://sima.usm.ac.id/histori_pendidikan/khs/save_bpm_khs"
            
            for i, form_html in enumerate(forms):
                def get_val(name):
                    pat = fr'name=["\']{name}["\'][^>]*value=["\']([^"\']+)["\']|value=["\']([^"\']+)["\'][^>]*name=["\']{name}["\']'
                    m = re.search(pat, form_html, re.IGNORECASE)
                    return m.group(1) or m.group(2) if m else None

                val_id_sem = get_val('id_semester')
                val_id_jad = get_val('id_jadwal')
                val_kd_khs = get_val('kode_khusus')
                val_id_prd = get_val('id_prodi')
                
                if val_id_sem and val_id_jad and val_kd_khs and val_id_prd:
                    payload_data = []
                    for q in range(1, 27):
                        payload_data.append(('id_semester', val_id_sem))
                        payload_data.append(('id_jadwal', val_id_jad))
                        payload_data.append(('kode_khusus', val_kd_khs))
                        payload_data.append(('id_prodi', val_id_prd))
                        payload_data.append(('id_ques[]', str(q)))
                        payload_data.append((f'skor[{q}]', '2'))

                    headers_post = session.headers.copy()
                    headers_post["Referer"] = full_url 
                    headers_post["Content-Type"] = "application/x-www-form-urlencoded"
                    try:
                        r_post = session.post(url_save, headers=headers_post, data=payload_data, timeout=15)
                    except: pass
        
        if not processed_any: return "✅ **Sudah Beres!**\nSemua Kuesioner/BPM sudah terisi."
            
    except Exception as e: return f"🐛 Error Scanning: {e}"
    
    if not results: return "✅ **Selesai!** BPM berhasil diisi."
    return "\n".join(results) + "\n\n✅ **Selesai!**"