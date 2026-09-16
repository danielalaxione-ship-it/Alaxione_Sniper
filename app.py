import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
import time

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

        # Extract text from reviews
        review_elements = page.query_selector_all('.wiI7pd')
        for el in review_elements:
            reviews_text.append(el.inner_text())

        if not reviews_text:
            # Fallback: extract all text
            reviews_text.append(page.inner_text('body'))

        browser.close()
    return " ".join(reviews_text)

def generate_pitch(reviews):
    pitch = "Argumentaire Commercial :\n\n"
    reviews_lower = reviews.lower()

    phone_issues = any(keyword in reviews_lower for keyword in ['téléphone', 'telephone', 'joindre', 'répond pas', 'repond pas', 'raccroche', 'standard', 'secrétariat', 'appel'])
    wait_issues = any(keyword in reviews_lower for keyword in ['attente', 'retard', 'heures', 'attendre', 'long', 'patience'])

    if phone_issues and wait_issues:
        pitch += "Nous avons remarqué que vos patients se plaignent régulièrement du temps d'attente en salle et de la difficulté à joindre votre cabinet par téléphone. Notre solution d'agenda en ligne et de télésecrétariat peut vous aider à désengorger votre standard et optimiser votre planning tout en améliorant la satisfaction patient."
    elif phone_issues:
        pitch += "Nous avons remarqué que vos patients ont des difficultés à joindre votre cabinet par téléphone. Notre service de télésecrétariat médical ou notre standard automatisé peut prendre le relais pour que vous ne perdiez plus aucun appel et libériez l'esprit de votre équipe."
    elif wait_issues:
        pitch += "Nous avons remarqué que vos patients mentionnent souvent des temps d'attente importants lors de leurs rendez-vous. Notre solution de prise de rendez-vous en ligne et de rappels par SMS permet de mieux lisser votre activité et de réduire l'attente en salle."
    else:
        pitch += "Vos patients semblent globalement satisfaits de votre pratique. Toutefois, la gestion quotidienne peut toujours être optimisée. Découvrez comment nos outils numériques peuvent vous faire gagner un temps administratif précieux au quotidien."

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

            st.write(f"**URL à analyser :** {url}")

            if st.button("Lancer l'extraction et générer l'argumentaire", type="primary"):
                with st.spinner('Extraction des avis Google Maps en cours (Playwright headless)...'):
                    try:
                        reviews = extract_reviews(url)
                        st.success("Extraction terminée avec succès !")

                        st.subheader("💡 Argumentaire généré")
                        pitch = generate_pitch(reviews)
                        st.info(pitch)

                        with st.expander("Voir le contenu brut extrait"):
                            st.write(reviews[:1500] + "..." if len(reviews) > 1500 else reviews)
                    except Exception as e:
                        st.error(f"Une erreur s'est produite lors de l'extraction via Playwright : {str(e)}")

    except Exception as e:
        st.error(f"Erreur de lecture du fichier CSV : {str(e)}")
else:
    st.info("👆 Veuillez importer un fichier CSV pour commencer.")
