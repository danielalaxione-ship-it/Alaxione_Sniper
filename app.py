import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time
import subprocess
import sys

def extract_reviews(url):
    reviews_text = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
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
            review_elements = page.query_selector_all('.wiI7pd')
            if review_elements:
                try:
                    review_elements[-1].scroll_into_view_if_needed()
                except:
                    pass
            time.sleep(1)

        # Extract text from reviews (up to 20)
        review_elements = page.query_selector_all('.wiI7pd')
        for el in review_elements[:20]:
            reviews_text.append(el.inner_text())

        if not reviews_text:
            # Fallback: extract all text
            reviews_text.append(page.inner_text('body'))

        browser.close()
    return reviews_text

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

    if issues_found:
        issues_str = " et ".join([", ".join(issues_found[:-1]), issues_found[-1]] if len(issues_found) > 1 else issues_found)
        pitch += f"Nous avons remarqué que vos patients mentionnent régulièrement {issues_str}. "
        pitch += "Notre solution globale Alaxione, avec son **agenda intelligent** et **SecrétarIA**, peut vous aider à résoudre ces problématiques de manière automatisée, afin de libérer du temps médical et d'optimiser l'organisation du cabinet."
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
                        reviews = extract_reviews(url)
                        st.success("Extraction terminée avec succès !")

                        st.subheader("💡 Argumentaire généré")
                        reviews_text_joined = " ".join(reviews)

                        note = selected_row[note_col] if note_col and pd.notna(selected_row[note_col]) else None
                        count = selected_row[avis_col] if avis_col and pd.notna(selected_row[avis_col]) else None

                        pitch = generate_pitch(reviews_text_joined, note=note, count=count)
                        st.info(pitch)

                        with st.expander("Voir le contenu brut extrait"):
                            for i, review in enumerate(reviews):
                                st.markdown(f"**Avis {i+1} :**")
                                st.write(review)
                                st.divider()
                    except Exception as e:
                        st.error(f"Une erreur s'est produite lors de l'extraction via Playwright : {str(e)}")

    except Exception as e:
        st.error(f"Erreur de lecture du fichier CSV : {str(e)}")
else:
    st.info("👆 Veuillez importer un fichier CSV pour commencer.")
