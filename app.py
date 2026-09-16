import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time
import subprocess
import sys

def extract_reviews(url):
    reviews_text = []
    reviews_dates = []
    with sync_playwright() as p:
        # Forcer le français avec locale et args
        browser = p.chromium.launch(headless=True, args=['--lang=fr-FR'])
        context = browser.new_context(locale="fr-FR")
        page = context.new_page()
        page.goto(url)
        time.sleep(3) # Wait for page to load

        # Try to accept cookies
        try:
            page.get_by_role("button", name="Tout accepter").click(timeout=2000)
        except:
            pass

        try:
            page.get_by_role("button", name="Accept all").click(timeout=2000)
        except:
            pass

        # Try to click on reviews tab
        try:
            page.get_by_role("tab", name="Avis").click(timeout=3000)
            time.sleep(2)
        except:
            pass

        try:
            page.get_by_role("tab", name="Reviews").click(timeout=3000)
            time.sleep(2)
        except:
            pass

        # Scroll to load more reviews
        for _ in range(5):
            review_elements = page.query_selector_all('.jftiEf')
            if review_elements:
                try:
                    review_elements[-1].scroll_into_view_if_needed()
                except:
                    pass
            time.sleep(1)

        # Extract text from reviews (up to 20)
        review_elements = page.query_selector_all('.jftiEf')
        for el in review_elements[:20]:
            text_el = el.query_selector('.wiI7pd')
            date_el = el.query_selector('.rsqaWe')

            # We want to skip reviews without text for pitch generation
            if text_el:
                reviews_text.append(text_el.inner_text())
                if date_el:
                    reviews_dates.append(date_el.inner_text())
                else:
                    reviews_dates.append("Date inconnue")

        browser.close()
    return reviews_text, reviews_dates

import re

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
        return "Fréquence très élevée (plusieurs avis très récents)."

    avg_per_month = count / max_months
    if avg_per_month >= 1:
        return f"environ {avg_per_month:.1f} avis par mois"
    else:
        avg_per_year = avg_per_month * 12
        return f"environ {avg_per_year:.1f} avis par an"


def generate_pitch(reviews, note=None, count=None):
    pitch = "Argumentaire Commercial :\n\n"

    if note and count:
        pitch += f"Avec une note de {note}/5 sur {count} avis, votre réputation en ligne reflète votre activité.\n\n"
    elif note:
        pitch += f"Avec une note de {note}/5, votre réputation en ligne est importante.\n\n"
    elif count:
        pitch += f"Avec {count} avis au total, vous avez une forte visibilité en ligne.\n\n"

    reviews_lower = reviews.lower()

    phone_issues = any(keyword in reviews_lower for keyword in ['téléphone', 'telephone', 'joindre', 'répond pas', 'repond pas', 'raccroche', 'standard', 'secrétariat', 'appel'])
    wait_issues = any(keyword in reviews_lower for keyword in ['attente', 'retard', 'heures', 'attendre', 'long', 'patience'])
    cancel_issues = any(keyword in reviews_lower for keyword in ['annule', 'annulation', 'annulé', 'dernière minute'])
    planning_issues = any(keyword in reviews_lower for keyword in ['planning', 'rendez-vous', 'rdv', 'date', 'créneau'])
    leave_issues = any(keyword in reviews_lower for keyword in ['congé', 'conge', 'vacances', 'remplaçant', 'absence'])

    issues_found = []

    if wait_issues:
        issues_found.append("du temps d'attente important")
    if phone_issues:
        issues_found.append("de la difficulté à joindre le cabinet")
    if cancel_issues:
        issues_found.append("des annulations de dernière minute")
    if planning_issues:
        issues_found.append("des problèmes de gestion de planning")
    if leave_issues:
        issues_found.append("des difficultés lors des périodes de congés")

    try:
        note_float = float(str(note).replace(',', '.')) if note is not None else 5.0
    except ValueError:
        note_float = 5.0

    is_low_rating = note_float < 3.5

    if issues_found or is_low_rating:
        if issues_found:
            issues_str = " et ".join([", ".join(issues_found[:-1]), issues_found[-1]] if len(issues_found) > 1 else issues_found)
            pitch += f"Nous avons remarqué que vos patients mentionnent régulièrement {issues_str}. "

        pitch += "Pour faire face à la dégradation de votre e-réputation et à la tension au cabinet avec des patients mécontents, il est nécessaire de s'appuyer sur **SecrétarIA** et un **agenda optimisé** pour apaiser la relation patient."
    else:
        pitch += "Bien que vos patients semblent globalement satisfaits de votre pratique, la gestion quotidienne peut toujours être optimisée. Les solutions Alaxione (agenda intelligent, SecrétarIA) peuvent vous faire gagner un temps administratif précieux au quotidien."

    return pitch

st.set_page_config(page_title="Sniper d'Avis", layout="wide")
st.title("🎯 Sniper d'Avis - Générateur d'argumentaire commercial")

st.markdown("""
Cette application vous permet d'importer une liste de médecins, d'analyser leurs avis Google Maps en temps réel,
et de générer un argumentaire commercial sur mesure axé sur les problèmes récurrents (ex: temps d'attente, secrétariat injoignable).
""")

uploaded_file = st.file_uploader("Importez votre fichier CSV de leads", type=['csv'])

if uploaded_file is not None:
    try:
        # Tente de lire le CSV (avec gestion basique du séparateur)
        df = pd.read_csv(uploaded_file, sep=None, engine='python')
        if 'URL_Google_Maps' not in df.columns:
            st.error("Le fichier CSV doit impérativement contenir une colonne nommée 'URL_Google_Maps'.")
        else:
            # Cherche une colonne pour le nom du médecin
            name_col = None
            for col in ['Nom', 'nom', 'Name', 'name', 'Docteur', 'Médecin', 'Medecin']:
                if col in df.columns:
                    name_col = col
                    break

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

            # Find Note and Nombre d'avis columns
            note_col = next((col for col in df.columns if col.lower() in ['note', 'rating', 'note_google', 'google_note']), None)
            avis_col = next((col for col in df.columns if 'avis' in col.lower() or 'reviews' in col.lower()), None)

            col1, col2 = st.columns(2)
            if note_col and pd.notna(selected_row[note_col]):
                col1.metric("Note Google", str(selected_row[note_col]))
            if avis_col and pd.notna(selected_row[avis_col]):
                col2.metric("Nombre total d'avis", str(selected_row[avis_col]))

            st.write(f"**URL à analyser :** {url}")

            if st.button("Lancer l'extraction et générer l'argumentaire", type="primary"):
                with st.spinner('Extraction des avis Google Maps en cours (Playwright headless)...'):
                    try:
                        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                        reviews, review_dates = extract_reviews(url)
                        st.success("Extraction terminée avec succès !")

                        # Affichage de la fréquence des avis
                        if review_dates:
                            freq_text = calculate_frequency(review_dates)
                            st.metric("Fréquence des avis récents", freq_text)

                        st.subheader("💡 Argumentaire généré")
                        reviews_text_joined = " ".join(reviews)

                        note = selected_row[note_col] if note_col and pd.notna(selected_row[note_col]) else None
                        count = selected_row[avis_col] if avis_col and pd.notna(selected_row[avis_col]) else None

                        pitch = generate_pitch(reviews_text_joined, note=note, count=count)
                        st.info(pitch)

                        with st.expander("Voir le contenu brut extrait"):
                            for i, (review, date) in enumerate(zip(reviews, review_dates)):
                                st.markdown(f"**Avis {i+1}** - *{date}*")
                                st.write(review)
                                st.divider()
                    except Exception as e:
                        st.error(f"Une erreur s'est produite lors de l'extraction via Playwright : {str(e)}")

    except Exception as e:
        st.error(f"Erreur de lecture du fichier CSV : {str(e)}")
else:
    st.info("👆 Veuillez importer un fichier CSV pour commencer.")
