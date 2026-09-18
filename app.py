import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time
import subprocess
import sys
import urllib.parse

def extract_reviews(url):
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    query['hl'] = ['fr']
    query['gl'] = ['FR']
    new_query = urllib.parse.urlencode(query, doseq=True)
    base_url = parsed._replace(query=new_query).geturl()

    max_retries = 3
    for attempt in range(max_retries):
        reviews_text = []
        reviews_dates = []
        reviews_responses = []
        gmb_data = {
            "website": "Absent",
            "hours": "Incomplets ou absents",
            "phone": "Absent",
            "category": "Générique",
            "appointment": "Absent",
            "title": "Nom propre"
        }

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--lang=fr-FR', '--window-size=1920,1080'])
                context = browser.new_context(
                    locale="fr-FR",
                    viewport={'width': 1920, 'height': 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.goto(base_url, wait_until='domcontentloaded', timeout=60000)

                try:
                    page.locator('button:has-text("Tout accepter"), button:has-text("Accept all")').first.click(timeout=3000)
                except:
                    pass

                time.sleep(2)

                # --- GMB Technical Audit Extraction ---
                try:
                    # 1. Title (Nom de la fiche)
                    title_el = page.locator('h1.DUwDvf')
                    if title_el.count() > 0:
                        title_text = title_el.first.inner_text().strip()
                        if len(title_text.split()) > 4 or "-" in title_text or "|" in title_text:
                            gmb_data["title"] = "Suroptimisé avec mots-clés"
                        else:
                            gmb_data["title"] = "Nom propre"

                    # 2. Category
                    category_btn = page.locator('button.DkEaL')
                    if category_btn.count() > 0:
                        cat_text = category_btn.first.inner_text().strip()
                        if cat_text:
                            gmb_data["category"] = "Précisée"

                    # 3. Phone
                    phone_btn = page.locator('button[data-tooltip*="téléphone"], button[data-tooltip*="phone"], button[data-item-id^="phone:"]')
                    if phone_btn.count() > 0:
                        gmb_data["phone"] = "Présent"

                    # 4. Website
                    website_btn = page.locator('a[data-item-id="authority"]')
                    if website_btn.count() > 0:
                        gmb_data["website"] = "Présent"

                    # 5. Appointment link
                    links = page.locator('a')
                    for i in range(links.count()):
                        try:
                            href = links.nth(i).get_attribute("href")
                            if href and any(domain in href.lower() for domain in ["doctolib", "maiia", "keldoc", "rdv", "rendez-vous"]):
                                gmb_data["appointment"] = "Présent"
                                break
                        except:
                            pass

                    # 6. Hours
                    if page.locator('div[aria-label*="ouvert"]').count() > 0 or \
                       page.locator('div[aria-label*="fermé"]').count() > 0 or \
                       page.locator('div[aria-label*="Horaires"]').count() > 0 or \
                       page.locator('div.OqCjIf[data-item-id="oh"]').count() > 0:
                        gmb_data["hours"] = "Complets"
                except:
                    pass
                # ----------------------------------------

                try:
                    # 1. Search for tab
                    tabs = page.locator('button[role="tab"]').all()
                    found_avis = False
                    for t in tabs:
                        if 'avis' in t.inner_text().lower() or 'reviews' in t.inner_text().lower():
                            t.click()
                            found_avis = True
                            time.sleep(2)
                            break

                    # 2. Search for Plus d'avis button
                    if not found_avis:
                        more = page.locator('button:has-text("Plus d\'avis")')
                        if more.count() > 0:
                            more.first.evaluate("node => node.click()")
                            found_avis = True
                            time.sleep(2)

                    # 3. Fallback to tab index
                    if not found_avis:
                        try:
                            tab_fallback = page.locator('button[role="tab"][data-tab-index="1"], button[role="tab"][data-tab-index="2"]')
                            if tab_fallback.count() > 0:
                                tab_fallback.first.click(timeout=3000)
                                time.sleep(2)
                        except:
                            pass

                    # Scroll dans les avis 2 ou 3 fois pour charger le texte
                    for _ in range(3):
                        try:
                            # On cible le dernier avis pour forcer le défilement et charger les suivants
                            reviews_loc = page.locator('.jftiEf')
                            if reviews_loc.count() > 0:
                                reviews_loc.last.scroll_into_view_if_needed(timeout=1000)
                        except:
                            pass

                        try:
                            # Fallback JS pour forcer le défilement des conteneurs
                            page.evaluate('''
                                () => {
                                    let mainDivs = document.querySelectorAll('div[role="main"]');
                                    mainDivs.forEach(d => d.scrollBy(0, 1000));

                                    let elements = document.querySelectorAll('.m6QErb');
                                    for (let el of elements) {
                                        if (el.scrollHeight > el.clientHeight) {
                                            el.scrollTop = el.scrollHeight;
                                            el.dispatchEvent(new Event('scroll'));
                                        }
                                    }
                                }
                            ''')
                        except:
                            pass
                        time.sleep(2)

                    try:
                        more_buttons = page.locator('button.w8nwRe.kyuRq')
                        for i in range(more_buttons.count()):
                            # Use evaluate click to bypass interception
                            more_buttons.nth(i).evaluate("node => node.click()")
                            time.sleep(0.5)
                    except:
                        pass
                except Exception as e:
                    print("Erreur globale sur l'extraction Playwright :", e)
                    pass

                try:
                    review_elements = page.query_selector_all('.jftiEf')
                    for el in review_elements[:20]:
                        text_el = el.query_selector('.wiI7pd')
                        date_el = el.query_selector('.rsqaWe')

                        response_el = el.query_selector('.CDe7pd')
                        has_response = False
                        if response_el:
                            has_response = True
                        else:
                            inner = el.inner_text()
                            if "Réponse du propriétaire" in inner or "Réponse de" in inner:
                                has_response = True

                        if text_el:
                            reviews_text.append(text_el.inner_text())
                            if date_el:
                                reviews_dates.append(date_el.inner_text())
                            else:
                                reviews_dates.append("Date inconnue")
                            reviews_responses.append(has_response)
                except Exception as e:
                    pass

                browser.close()

            # Check if extraction was successful to break the retry loop
            if len(reviews_text) > 0:
                break

        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                pass

    return reviews_text, reviews_dates, reviews_responses, gmb_data

def calculate_frequency(dates_str):
    max_months = 0
    count = len(dates_str)

    if count == 0:
        return "Pas assez de données pour calculer la fréquence."

    for d in dates_str:
        d = d.lower()
        months = 0
        if "jour" in d or "heure" in d or "minute" in d:
            months = 0
        elif "semaine" in d:
            num = re.search(r'\d+', d)
            val = int(num.group()) if num else 1
            months = val / 4.0
        elif "mois" in d:
            num = re.search(r'\d+', d)
            val = int(num.group()) if num else 1
            months = val
        elif "an" in d or "année" in d or "annee" in d:
            if "un " in d or "une " in d:
                val = 1
            else:
                num = re.search(r'\d+', d)
                val = int(num.group()) if num else 1
            months = val * 12

        if months > max_months:
            max_months = months

    if max_months == 0:
        return "plusieurs avis très récents"

    avg_per_month = count / max_months
    if avg_per_month >= 1:
        return f"environ {avg_per_month:.1f} avis par mois"
    elif avg_per_month >= 0.25:
        avg_per_quarter = avg_per_month * 3
        return f"environ {avg_per_quarter:.1f} avis par trimestre"
    else:
        avg_per_year = avg_per_month * 12
        return f"environ {avg_per_year:.1f} avis par an"


def generate_pitch(reviews_list, note=None, count=None):
    pitch = "Analyse des Tendances :\n\n"

    if note and count:
        pitch += f"Avec une note de {note}/5 sur {count} avis, voici l'analyse des points de douleur soulevés par vos patients.\n\n"
    elif note:
        pitch += f"Avec une note de {note}/5, voici l'analyse des points de douleur soulevés par vos patients.\n\n"
    elif count:
        pitch += f"Avec {count} avis au total, voici l'analyse des points de douleur soulevés par vos patients.\n\n"
    else:
        pitch += f"Voici l'analyse des points de douleur soulevés par vos patients.\n\n"

    if not reviews_list:
        pitch += "Aucun avis textuel n'a pu être extrait pour l'analyse.\n"
        return pitch

    total_reviews = len(reviews_list)
    phone_issues_count = 0
    wait_issues_count = 0
    cancel_issues_count = 0
    planning_issues_count = 0
    leave_issues_count = 0

    phone_keywords = ['téléphone', 'telephone', 'joindre', 'répond pas', 'repond pas', 'raccroche', 'standard', 'secrétariat', 'appel']
    wait_keywords = ['attente', 'retard', 'heures', 'attendre', 'long', 'patience']
    cancel_keywords = ['annule', 'annulation', 'annulé', 'dernière minute']
    planning_keywords = ['planning', 'rendez-vous', 'rdv', 'date', 'créneau']
    leave_keywords = ['congé', 'conge', 'vacances', 'remplaçant', 'absence']

    for review in reviews_list:
        rev_lower = review.lower()
        if any(keyword in rev_lower for keyword in phone_keywords):
            phone_issues_count += 1
        if any(keyword in rev_lower for keyword in wait_keywords):
            wait_issues_count += 1
        if any(keyword in rev_lower for keyword in cancel_keywords):
            cancel_issues_count += 1
        if any(keyword in rev_lower for keyword in planning_keywords):
            planning_issues_count += 1
        if any(keyword in rev_lower for keyword in leave_keywords):
            leave_issues_count += 1

    stats_found = False

    if wait_issues_count > 0:
        pct = int((wait_issues_count / total_reviews) * 100)
        pitch += f"- **{pct}%** des avis signalent des problèmes de retard ou de temps d'attente.\n"
        stats_found = True

    if phone_issues_count > 0:
        pct = int((phone_issues_count / total_reviews) * 100)
        pitch += f"- **{pct}%** des avis signalent des difficultés à joindre le secrétariat par téléphone.\n"
        stats_found = True

    if planning_issues_count > 0:
        pct = int((planning_issues_count / total_reviews) * 100)
        pitch += f"- **{pct}%** des avis signalent des problèmes liés à la gestion du planning (rendez-vous, créneaux).\n"
        stats_found = True

    if cancel_issues_count > 0:
        pct = int((cancel_issues_count / total_reviews) * 100)
        pitch += f"- **{pct}%** des avis mentionnent des annulations (parfois de dernière minute).\n"
        stats_found = True

    if leave_issues_count > 0:
        pct = int((leave_issues_count / total_reviews) * 100)
        pitch += f"- **{pct}%** des avis signalent des difficultés lors des périodes de congés ou d'absence.\n"
        stats_found = True

    pitch += "\n"

    return pitch

st.set_page_config(page_title="Sniper d'Avis", layout="wide")
st.title("🎯 Sniper d'Avis - Outil d'Audit Factuel et Technique")

st.markdown("""
Cette application vous permet d'importer une liste de médecins, d'analyser leurs avis Google Maps en temps réel,
et de générer un audit factuel et technique (taux de réponse, indicateurs GMB, analyse des points de douleur).
""")

mode = st.radio("Choisissez le mode d'analyse :", ["Analyse Unitaire", "Analyse en Masse (Fichier CSV)"])

uploaded_file = st.file_uploader("Importez votre fichier CSV de leads", type=['csv'])

if uploaded_file is not None:
    try:
        # Tente de lire le CSV (avec gestion basique du séparateur)
        df = pd.read_csv(uploaded_file, sep=None, engine='python')
        if 'URL_Google_Maps' not in df.columns:
            st.error("Le fichier CSV doit impérativement contenir une colonne nommée 'URL_Google_Maps'.")
        else:
            # Sécurisation : retirer les doublons sur l'URL
            df = df.drop_duplicates(subset=['URL_Google_Maps']).reset_index(drop=True)

            # Cherche une colonne pour le nom du médecin
            name_col = None
            for col in ['Nom', 'nom', 'Name', 'name', 'Docteur', 'Médecin', 'Medecin']:
                if col in df.columns:
                    name_col = col
                    break

            # Find Note and Nombre d'avis columns
            note_col = next((col for col in df.columns if col.lower() in ['note', 'rating', 'note_google', 'google_note']), None)
            avis_col = next((col for col in df.columns if 'avis' in col.lower() or 'reviews' in col.lower()), None)

            if mode == "Analyse Unitaire":
                if name_col:
                    # Création du selectbox avec les noms
                    options = df[name_col].astype(str).tolist()
                    selected_option = st.selectbox("Sélectionnez un médecin", options)
                    selected_row = df[df[name_col].astype(str) == selected_option].iloc[0]
                else:
                    # Création du selectbox avec les index
                    options = df.index.tolist()
                    selected_option = st.selectbox("Sélectionnez un médecin (par index)", options)
                    selected_row = df.iloc[selected_option]

                url = selected_row['URL_Google_Maps']

                col1, col2 = st.columns(2)
                if note_col and pd.notna(selected_row[note_col]):
                    col1.metric("Note Google", str(selected_row[note_col]))
                if avis_col and pd.notna(selected_row[avis_col]):
                    col2.metric("Nombre total d'avis", str(selected_row[avis_col]))

                st.write(f"**URL à analyser :** {url}")

                if st.button("Lancer l'extraction et générer l'audit", type="primary"):
                    with st.spinner('Extraction des avis Google Maps en cours (Playwright headless)...'):
                        try:
                            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                            reviews, review_dates, review_responses, gmb_data = extract_reviews(url)
                            st.success("Extraction terminée avec succès !")

                            # Taux de réponse
                            if review_responses:
                                nb_responses = sum(review_responses)
                                total_extracted = len(review_responses)
                                response_rate = (nb_responses / total_extracted) * 100
                                response_text = f"Oui ({response_rate:.0f}%)" if response_rate > 0 else "Non"
                            else:
                                response_text = "N/A"

                            # Affichage de la fréquence des avis et Taux de réponse
                            col_freq, col_resp = st.columns(2)
                            with col_freq:
                                if review_dates:
                                    freq_text = calculate_frequency(review_dates)
                                    st.metric("Fréquence des avis", freq_text)
                            with col_resp:
                                st.metric("Taux de réponse du praticien", response_text)

                            st.subheader("📋 Audit Technique GMB")
                            gmb_df = pd.DataFrame({
                                "Indicateur": ["Site Web", "Horaires complets", "Numéro de téléphone", "Spécialité / Catégorie principale", "Lien de prise de rendez-vous (ex: Doctolib)", "Nom de la fiche"],
                                "Statut": [
                                    gmb_data.get("website", "Absent"),
                                    gmb_data.get("hours", "Incomplets ou absents"),
                                    gmb_data.get("phone", "Absent"),
                                    gmb_data.get("category", "Générique"),
                                    gmb_data.get("appointment", "Absent"),
                                    gmb_data.get("title", "Nom propre")
                                ]
                            })
                            st.table(gmb_df)

                            st.subheader("📊 Analyse des Tendances")

                            note = selected_row[note_col] if note_col and pd.notna(selected_row[note_col]) else None
                            count = selected_row[avis_col] if avis_col and pd.notna(selected_row[avis_col]) else None

                            pitch = generate_pitch(reviews, note=note, count=count)
                            st.info(pitch)

                        except Exception as e:
                            st.error(f"Une erreur s'est produite lors de l'extraction via Playwright : {str(e)}")

            else:  # Analyse en Masse
                st.write(f"**Nombre de prospects à analyser :** {len(df)}")

                if st.button("Lancer l'analyse en masse", type="primary"):
                    try:
                        with st.spinner('Installation des dépendances navigateur...'):
                            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                    except Exception as e:
                        st.error(f"Erreur d'installation de Playwright : {e}")

                    # Initialize new columns
                    df["Sniper_Note_Globale"] = ""
                    df["Sniper_Volume_Avis"] = ""
                    df["Sniper_Frequence"] = ""
                    df["Sniper_Taux_Reponse"] = ""
                    df["Sniper_Top_Pain_Point"] = ""
                    df["Sniper_Resume_Audit"] = ""

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    total_rows = len(df)

                    for idx, row in df.iterrows():
                        i = idx + 1
                        prospect_name = row[name_col] if name_col and pd.notna(row[name_col]) else f"Index {idx}"
                        status_text.text(f"Traitement : {prospect_name} ({i}/{total_rows})...")

                        url = row['URL_Google_Maps']
                        if pd.isna(url) or not isinstance(url, str):
                            df.at[idx, "Sniper_Resume_Audit"] = "Erreur : URL manquante ou invalide"
                            progress_bar.progress(i / total_rows)
                            continue

                        try:
                            reviews, review_dates, review_responses, gmb_data = extract_reviews(url)

                            # Note Globale & Volume Avis
                            note = row[note_col] if note_col and pd.notna(row[note_col]) else None
                            count = row[avis_col] if avis_col and pd.notna(row[avis_col]) else None
                            df.at[idx, "Sniper_Note_Globale"] = str(note) if note else "N/A"
                            df.at[idx, "Sniper_Volume_Avis"] = str(count) if count else "N/A"

                            # Fréquence
                            freq_text = "N/A"
                            if review_dates:
                                freq_text = calculate_frequency(review_dates)
                            df.at[idx, "Sniper_Frequence"] = freq_text

                            # Taux de réponse
                            if review_responses:
                                nb_responses = sum(review_responses)
                                total_extracted = len(review_responses)
                                response_rate = (nb_responses / total_extracted) * 100
                                response_text = f"Oui ({response_rate:.0f}%)" if response_rate > 0 else "Non"
                            else:
                                response_text = "N/A"
                            df.at[idx, "Sniper_Taux_Reponse"] = response_text

                            # Pitch / Pain Point
                            pitch = generate_pitch(reviews, note=note, count=count)
                            pitch_clean = pitch.replace('\n', ' ').replace('\r', '')
                            df.at[idx, "Sniper_Top_Pain_Point"] = pitch_clean

                            # Audit Resume
                            audit_resume = f"Site: {gmb_data.get('website', 'N/A')} | Horaires: {gmb_data.get('hours', 'N/A')} | Tel: {gmb_data.get('phone', 'N/A')} | Cat: {gmb_data.get('category', 'N/A')} | RDV: {gmb_data.get('appointment', 'N/A')} | Nom: {gmb_data.get('title', 'N/A')}"
                            df.at[idx, "Sniper_Resume_Audit"] = audit_resume.replace('\n', ' ').replace('\r', '')

                        except Exception as e:
                            df.at[idx, "Sniper_Note_Globale"] = "Erreur"
                            df.at[idx, "Sniper_Volume_Avis"] = "Erreur"
                            df.at[idx, "Sniper_Frequence"] = "Erreur"
                            df.at[idx, "Sniper_Taux_Reponse"] = "Erreur"
                            df.at[idx, "Sniper_Top_Pain_Point"] = "Erreur"
                            df.at[idx, "Sniper_Resume_Audit"] = "Erreur"
                            # Continue to next prospect

                        progress_bar.progress(i / total_rows)
                        time.sleep(0.5)

                    status_text.text("Traitement terminé !")
                    st.success("Analyse en masse terminée !")

                    csv_export = df.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 Télécharger les résultats (CSV)",
                        data=csv_export,
                        file_name="resultats_analyse_masse.csv",
                        mime="text/csv"
                    )

    except Exception as e:
        st.error(f"Erreur de lecture du fichier CSV : {str(e)}")
else:
    st.info("👆 Veuillez importer un fichier CSV pour commencer.")
