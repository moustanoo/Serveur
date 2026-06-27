import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. CONNEXION À GOOGLE SHEETS
# ==========================================
@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    sheet = client.open_by_url(st.secrets["google_sheet"]["url"]).sheet1
    return sheet

sheet = init_connection()

def load_data():
    raw_data = sheet.get_all_values()
    
    if not raw_data or len(raw_data) <= 1:
        return pd.DataFrame(columns=['ID', 'Serveur', 'Date', 'Midi_Debut', 'Midi_Fin', 'Midi_Pause', 'Soir_Debut', 'Soir_Fin', 'Soir_Pause', 'Total_Heures'])
    
    headers = raw_data.pop(0)
    df = pd.DataFrame(raw_data, columns=headers)
    
    df['Date'] = df['Date'].astype(str)
    
    if 'Total_Heures' in df.columns:
        df['Total_Heures'] = df['Total_Heures'].astype(str).str.replace(',', '.').str.replace(' ', '')
        df['Total_Heures'] = pd.to_numeric(df['Total_Heures'], errors='coerce').fillna(0.0).astype(float)
        
    if 'Midi_Pause' in df.columns:
        df['Midi_Pause'] = pd.to_numeric(df['Midi_Pause'], errors='coerce').fillna(0).astype(int)
        
    if 'Soir_Pause' in df.columns:
        df['Soir_Pause'] = pd.to_numeric(df['Soir_Pause'], errors='coerce').fillna(0).astype(int)
        
    if 'ID' in df.columns:
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
        
    return df

def save_data(df):
    sheet.clear()
    sheet.update(values=[df.columns.values.tolist()] + df.values.tolist())

# ==========================================
# 2. LOGIQUE MÉTIER & CALCULS
# ==========================================
def calculer_duree_service(debut_str, fin_str, pause):
    if not debut_str or not fin_str or debut_str == "-" or fin_str == "-":
        return 0.0
    try:
        debut = datetime.strptime(debut_str, '%H:%M').time()
        fin = datetime.strptime(fin_str, '%H:%M').time()
        dummy_date = date.today()
        dt_debut = datetime.combine(dummy_date, debut)
        dt_fin = datetime.combine(dummy_date, fin)

        if dt_fin <= dt_debut:
            dt_fin += timedelta(days=1)

        duree_secondes = (dt_fin - dt_debut).total_seconds()
        duree_heures = duree_secondes / 3600.0
        duree_heures -= float(pause) / 60.0 
        return max(0.0, round(duree_heures, 2))
    except:
        return 0.0

def generer_heures_midi():
    heures = []
    for h in range(8, 18):
        heures.extend([f"{h:02d}:00", f"{h:02d}:15", f"{h:02d}:30", f"{h:02d}:45"])
    heures.append("18:00")
    return heures

def generer_heures_soir():
    heures = []
    for h in range(17, 24):
        heures.extend([f"{h:02d}:00", f"{h:02d}:15", f"{h:02d}:30", f"{h:02d}:45"])
    heures.extend(["00:00", "00:15", "00:30", "00:45", "01:00"])
    return heures

heures_midi_options = generer_heures_midi() + ["-"]
heures_soir_options = generer_heures_soir() + ["-"]

# ==========================================
# 3. INTERFACE UTILISATEUR ET MÉMOIRE
# ==========================================
st.set_page_config(page_title="Gestion des Heures", layout="wide")

if 'admin_connecte' not in st.session_state:
    st.session_state['admin_connecte'] = False

# NOUVEAU : Le compteur de rafraîchissement
if 'reset_counter' not in st.session_state:
    st.session_state['reset_counter'] = 0

def reinitialiser_cases():
    """Incrémente le compteur pour forcer la création de nouvelles cases vides"""
    st.session_state['reset_counter'] += 1

onglet_saisie, onglet_admin = st.tabs(["🕒 Saisir mes heures", "📊 Administration"])

# --- ONGLET 1 : SAISIE ---
with onglet_saisie:
    st.header("Pointage des services")
    
    # Affichage du message de succès (s'il existe) puis on l'efface
    if 'message_succes' in st.session_state:
        st.success(st.session_state['message_succes'])
        del st.session_state['message_succes'] 
    
    nom_serveur = st.text_input("Nom du serveur", placeholder="Ex: Amélie")
    
    # Quand on change la date, ça déclenche instantanément la fonction reinitialiser_cases
    date_service = st.date_input("Date du(des) service(s)", format="DD/MM/YYYY", on_change=reinitialiser_cases)
    
    st.write("### Quels services as-tu fait ce jour-là ?")
    
    # NOUVEAU : On intègre le compteur dans la "clé" des cases
    midi_coche = st.checkbox("☀️ Service du Midi (08h - 18h)", key=f"check_midi_{st.session_state['reset_counter']}")
    soir_coche = st.checkbox("🌙 Service du Soir (17h - 01h)", key=f"check_soir_{st.session_state['reset_counter']}")

    debut_midi, fin_midi, pause_midi = "-", "-", 0
    debut_soir, fin_soir, pause_soir = "-", "-", 0

    if midi_coche:
        st.markdown("**Horaires du Midi**")
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            debut_midi = st.selectbox("Début (Midi)", generer_heures_midi(), index=8)
        with col_m2:
            fin_midi = st.selectbox("Fin (Midi)", generer_heures_midi(), index=24)
        with col_m3:
            pause_midi = st.number_input("Pause Midi (min)", min_value=0, max_value=120, value=0, step=5, key=f"p_midi_{st.session_state['reset_counter']}")
            
    if soir_coche:
        st.markdown("**Horaires du Soir**")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            debut_soir = st.selectbox("Début (Soir)", generer_heures_soir(), index=4)
        with col_s2:
            fin_soir = st.selectbox("Fin (Soir)", generer_heures_soir(), index=len(generer_heures_soir())-1)
        with col_s3:
            pause_soir = st.number_input("Pause Soir (min)", min_value=0, max_value=120, value=0, step=5, key=f"p_soir_{st.session_state['reset_counter']}")

    if st.button("Enregistrer mes heures", type="primary"):
        if not nom_serveur:
            st.error("⚠️ Merci de renseigner ton nom avant d'enregistrer.")
        elif not midi_coche and not soir_coche:
            st.error("⚠️ Tu dois sélectionner au moins un service (Midi ou Soir).")
        else:
            with st.spinner("Sauvegarde dans Google Sheets..."):
                df = load_data()
                
                mask = (df['Serveur'] == nom_serveur) & (df['Date'] == str(date_service))
                
                if mask.any():
                    idx = df[mask].index[0]
                    if not midi_coche:
                        debut_midi, fin_midi, pause_midi = df.at[idx, 'Midi_Debut'], df.at[idx, 'Midi_Fin'], df.at[idx, 'Midi_Pause']
                    if not soir_coche:
                        debut_soir, fin_soir, pause_soir = df.at[idx, 'Soir_Debut'], df.at[idx, 'Soir_Fin'], df.at[idx, 'Soir_Pause']

                total_midi = calculer_duree_service(debut_midi, fin_midi, pause_midi)
                total_soir = calculer_duree_service(debut_soir, fin_soir, pause_soir)
                total_journee = float(round(total_midi + total_soir, 2))

                if mask.any():
                    idx = df[mask].index[0]
                    df.at[idx, 'Midi_Debut'] = debut_midi
                    df.at[idx, 'Midi_Fin'] = fin_midi
                    df.at[idx, 'Midi_Pause'] = int(pause_midi)
                    df.at[idx, 'Soir_Debut'] = debut_soir
                    df.at[idx, 'Soir_Fin'] = fin_soir
                    df.at[idx, 'Soir_Pause'] = int(pause_soir)
                    df.at[idx, 'Total_Heures'] = total_journee
                else:
                    nouveau_id = 1 if df.empty else pd.to_numeric(df['ID']).max() + 1
                    nouvelle_ligne = {
                        'ID': nouveau_id, 'Serveur': nom_serveur, 'Date': str(date_service),
                        'Midi_Debut': debut_midi, 'Midi_Fin': fin_midi, 'Midi_Pause': int(pause_midi),
                        'Soir_Debut': debut_soir, 'Soir_Fin': fin_soir, 'Soir_Pause': int(pause_soir),
                        'Total_Heures': total_journee
                    }
                    df = pd.concat([df, pd.DataFrame([nouvelle_ligne])], ignore_index=True)
                
                save_data(df)
                
                # On stocke le message de réussite, on augmente le compteur, et on redémarre la page
                st.session_state['message_succes'] = f"✅ Horaires enregistrés avec succès ! Total : {total_journee} h"
                reinitialiser_cases()
                st.rerun()

# --- ONGLET 2 : ADMINISTRATION ---
with onglet_admin:
    if not st.session_state['admin_connecte']:
        st.header("🔒 Accès Restreint")
        mot_de_passe = st.text_input("Mot de passe", type="password")
        if st.button("Se connecter"):
            if mot_de_passe == "Tabasco2024": 
                st.session_state['admin_connecte'] = True
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect.")
    else:
        col_titre, col_btn = st.columns([4, 1])
        with col_titre:
            st.header("Tableau de bord gérant")
        with col_btn:
            if st.button("🚪 Déconnexion"):
                st.session_state['admin_connecte'] = False
                st.rerun()

        st.write("💡 *Modifie les heures ou coche la case 'Supprimer' pour effacer une ligne, puis clique sur Enregistrer.*")
        
        col_mois, col_annee = st.columns(2)
        with col_mois:
            mois_selectionne = st.selectbox("Mois", range(1, 13), index=date.today().month - 1)
        with col_annee:
            annee_selectionnee = st.number_input("Année", min_value=2024, max_value=2030, value=date.today().year)

        df = load_data()
        
        if not df.empty:
            masque_date = df['Date'].str[5:7] == f"{mois_selectionne:02d}"
            masque_annee = df['Date'].str[0:4] == str(annee_selectionnee)
            df_filtre = df[masque_date & masque_annee].copy()

            if not df_filtre.empty:
                df_filtre.insert(0, '🗑️ Supprimer', False)

                edited_df = st.data_editor(
                    df_filtre,
                    column_config={
                        "🗑️ Supprimer": st.column_config.CheckboxColumn("Supprimer", help="Coche pour supprimer la ligne"),
                        "ID": st.column_config.NumberColumn("ID", disabled=True),
                        "Serveur": st.column_config.TextColumn("Serveur"),
                        "Date": st.column_config.TextColumn("Date"),
                        "Midi_Debut": st.column_config.SelectboxColumn("Midi Début", options=heures_midi_options),
                        "Midi_Fin": st.column_config.SelectboxColumn("Midi Fin", options=heures_midi_options),
                        "Midi_Pause": st.column_config.NumberColumn("Midi Pause", min_value=0, max_value=120, step=5),
                        "Soir_Debut": st.column_config.SelectboxColumn("Soir Début", options=heures_soir_options),
                        "Soir_Fin": st.column_config.SelectboxColumn("Soir Fin", options=heures_soir_options),
                        "Soir_Pause": st.column_config.NumberColumn("Soir Pause", min_value=0, max_value=120, step=5),
                        "Total_Heures": st.column_config.NumberColumn("Total Heures", disabled=True, format="%.2f h")
                    },
                    hide_index=True,
                    width='stretch'
                )

                if st.button("💾 Enregistrer les modifications", type="primary"):
                    with st.spinner("Mise à jour de Google Sheets..."):
                        
                        ids_a_supprimer = edited_df[edited_df['🗑️ Supprimer'] == True]['ID'].tolist()
                        
                        if ids_a_supprimer:
                            df = df[~df['ID'].isin(ids_a_supprimer)]
                        
                        lignes_a_garder = edited_df[edited_df['🗑️ Supprimer'] == False]
                        
                        for index, row in lignes_a_garder.iterrows():
                            t_midi = calculer_duree_service(row['Midi_Debut'], row['Midi_Fin'], row['Midi_Pause'])
                            t_soir = calculer_duree_service(row['Soir_Debut'], row['Soir_Fin'], row['Soir_Pause'])
                            nouveau_total = float(round(t_midi + t_soir, 2))
                            
                            idx_original = df[df['ID'] == row['ID']].index[0]
                            df.loc[idx_original, 'Midi_Debut'] = row['Midi_Debut']
                            df.loc[idx_original, 'Midi_Fin'] = row['Midi_Fin']
                            df.loc[idx_original, 'Midi_Pause'] = int(row['Midi_Pause'])
                            df.loc[idx_original, 'Soir_Debut'] = row['Soir_Debut']
                            df.loc[idx_original, 'Soir_Fin'] = row['Soir_Fin']
                            df.loc[idx_original, 'Soir_Pause'] = int(row['Soir_Pause'])
                            df.loc[idx_original, 'Total_Heures'] = nouveau_total

                        save_data(df)
                        
                        if ids_a_supprimer:
                            st.success(f"🗑️ {len(ids_a_supprimer)} ligne(s) supprimée(s) avec succès !")
                        else:
                            st.success("🎉 Modifications enregistrées avec succès !")
                        st.rerun()

                st.markdown("---")
                st.subheader("Total cumulé sur le mois (Rapports de Paie)")
                lignes_valides = edited_df[edited_df['🗑️ Supprimer'] == False]
                resume_serveurs = lignes_valides.groupby('Serveur')['Total_Heures'].sum().reset_index()
                resume_serveurs.columns = ['Serveur', 'Total Mensuel Validé (Heures)']
                st.dataframe(resume_serveurs, width='stretch', hide_index=True)
            else:
                st.info("Aucune heure enregistrée pour ce mois-ci.")
        else:
            st.info("La base de données est vide.")
