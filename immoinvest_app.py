import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import pandas as pd

# -----------------------------
# Finance helpers
# -----------------------------

def mensualite_credit(capital, taux_annuel, duree_annees):
    """Mensualité d’un crédit à annuités constantes (hors assurance)."""
    n = int(duree_annees) * 12
    taux_mensuel = float(taux_annuel) / 12.0
    if n <= 0:
        return 0.0
    if abs(taux_mensuel) < 1e-12:
        return float(capital) / n
    return float(capital) * (taux_mensuel / (1 - (1 + taux_mensuel) ** -n))

def tableau_amortissement(capital, taux_annuel, duree_annees):
    """Retourne un DataFrame mensuel: mois, annee, mensualite, interets, principal, crd."""
    n = int(duree_annees) * 12
    if n <= 0:
        return pd.DataFrame(columns=["month_index","year","month","payment","interest","principal","balance"])
    r = float(taux_annuel) / 12.0
    m = mensualite_credit(capital, taux_annuel, duree_annees)
    rows = []
    balance = float(capital)
    for i in range(1, n+1):
        interest = balance * r
        principal = max(m - interest, 0.0)
        balance = max(0.0, balance - principal)
        year = (i - 1) // 12 + 1
        month = (i - 1) % 12 + 1
        rows.append([i, year, month, m, interest, principal, balance])
    df = pd.DataFrame(rows, columns=["month_index","year","month","payment","interest","principal","balance"])
    return df

# -----------------------------
# Hypothèses (scénarios A/B)
# -----------------------------

class HypScenario:
    def __init__(self, name="A"):
        self.name = name
        # Revenus
        self.revalo_loyers = 0.015      # 1.5%/an
        # Charges - indexation distincte
        self.idx_assurance = 0.010
        self.idx_copro = 0.010
        self.idx_taxe = 0.012
        self.idx_assu_empr = 0.010
        self.idx_autres = 0.010
        # Fiscalité
        self.tmi = 0.30                 # 30%
        self.ps = 0.172                 # 17.2% prélèvements sociaux
        # Horizon
        self.duree_projection = 15      # années

    def as_dict(self):
        return {
            "revalo_loyers": self.revalo_loyers,
            "idx_assurance": self.idx_assurance,
            "idx_copro": self.idx_copro,
            "idx_taxe": self.idx_taxe,
            "idx_assu_empr": self.idx_assu_empr,
            "idx_autres": self.idx_autres,
            "tmi": self.tmi,
            "ps": self.ps,
            "duree_projection": self.duree_projection,
        }

# -----------------------------
# Application
# -----------------------------

class ImmoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestion Multi-Biens Immobiliers — v1.2 (Scénarios A/B, PS, indexations séparées)")
        self.geometry("1440x900")

        self.biens = []  # liste de dicts
        self.hypA = HypScenario("A")
        self.hypB = HypScenario("B")
        self.current_scenario = tk.StringVar(value="A")
        self.overlay_AB = tk.BooleanVar(value=False)

        # Top bar
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Button(top, text="Ajouter un bien", command=self.add_bien).pack(side="left", padx=4)
        ttk.Button(top, text="Amortissement (par bien)", command=self.show_amortissement_dialog).pack(side="left", padx=4)
        ttk.Button(top, text="Hypothèses Scénario A", command=lambda: self.edit_hypotheses("A")).pack(side="left", padx=4)
        ttk.Button(top, text="Hypothèses Scénario B", command=lambda: self.edit_hypotheses("B")).pack(side="left", padx=4)
        ttk.Label(top, text="Scénario affiché:").pack(side="left", padx=(16,4))
        ttk.Combobox(top, textvariable=self.current_scenario, values=["A","B"], width=4, state="readonly").pack(side="left")
        ttk.Checkbutton(top, text="Superposer A & B (totaux)", variable=self.overlay_AB).pack(side="left", padx=10)
        ttk.Button(top, text="Synthèse & projection", command=self.show_projection).pack(side="left", padx=10)

        self.status = ttk.Label(self, text="Ajoutez vos biens, définissez les hypothèses A/B, puis lancez la synthèse.", anchor="w")
        self.status.pack(fill="x", padx=10, pady=4)

        # Liste simple des biens (aperçu)
        self.tree_biens = ttk.Treeview(self, columns=("Nom","Emprunt","Durée","Taux","Loyer","Mensualité"), show="headings", height=8)
        for col in ("Nom","Emprunt","Durée","Taux","Loyer","Mensualité"):
            self.tree_biens.heading(col, text=col)
            self.tree_biens.column(col, width=160, anchor="center")
        self.tree_biens.pack(fill="x", padx=10, pady=6)

    # -------- Hypothèses --------

    def edit_hypotheses(self, which="A"):
        hyp = self.hypA if which == "A" else self.hypB
        win = tk.Toplevel(self)
        win.title(f"Hypothèses — Scénario {which}")
        win.geometry("520x520")

        items = [
            ("Revalorisation loyers (%)", "revalo_loyers", hyp.revalo_loyers*100),
            ("Indexation Assurance (%)", "idx_assurance", hyp.idx_assurance*100),
            ("Indexation Copropriété (%)", "idx_copro", hyp.idx_copro*100),
            ("Indexation Taxe foncière (%)", "idx_taxe", hyp.idx_taxe*100),
            ("Indexation Assu emprunteur (%)", "idx_assu_empr", hyp.idx_assu_empr*100),
            ("Indexation Autres charges (%)", "idx_autres", hyp.idx_autres*100),
            ("TMI (%)", "tmi", hyp.tmi*100),
            ("Prélèvements sociaux (%)", "ps", hyp.ps*100),
            ("Durée projection (années)", "duree_projection", hyp.duree_projection),
        ]

        entries = {}
        for i,(label,key,val) in enumerate(items):
            ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=6)
            e = ttk.Entry(win, width=18)
            e.insert(0, str(round(val,3)))
            e.grid(row=i, column=1, padx=8, pady=6)
            entries[key] = e

        def save():
            try:
                hyp.revalo_loyers   = float(entries["revalo_loyers"].get())/100.0
                hyp.idx_assurance   = float(entries["idx_assurance"].get())/100.0
                hyp.idx_copro       = float(entries["idx_copro"].get())/100.0
                hyp.idx_taxe        = float(entries["idx_taxe"].get())/100.0
                hyp.idx_assu_empr   = float(entries["idx_assu_empr"].get())/100.0
                hyp.idx_autres      = float(entries["idx_autres"].get())/100.0
                hyp.tmi             = float(entries["tmi"].get())/100.0
                hyp.ps              = float(entries["ps"].get())/100.0
                hyp.duree_projection= int(float(entries["duree_projection"].get()))
                messagebox.showinfo("OK", f"Hypothèses {which} mises à jour.")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", f"Valeurs invalides : {e}")

        ttk.Button(win, text="Enregistrer", command=save).grid(row=len(items), column=0, columnspan=2, pady=10)

    # -------- Biens --------

    def add_bien(self):
        win = tk.Toplevel(self)
        win.title("Nouveau bien / Modifier bien")
        win.geometry("560x560")

        labels = [
            ("Nom", "nom"),
            ("Prix achat (€)", "prix"),
            ("Montant emprunté (€)", "emprunt"),
            ("Durée crédit (années)", "duree"),
            ("Taux crédit (%)", "taux"),
            ("Loyer annuel (€)", "loyer"),
            ("Assurance (€)", "assurance"),
            ("Taxe foncière (€)", "taxe_fonciere"),
            ("Copropriété (€)", "copro"),
            ("Assurance emprunteur (€)", "assurance_emprunteur"),
            ("Autres charges (€)", "autres"),
        ]

        entries = {}
        for i, (lab, key) in enumerate(labels):
            ttk.Label(win, text=lab).grid(row=i, column=0, sticky="w", padx=8, pady=6)
            e = ttk.Entry(win, width=26)
            e.grid(row=i, column=1, padx=8, pady=6, sticky="we")
            entries[key] = e

        def save():
            try:
                bien = {
                    "nom": entries["nom"].get().strip() or f"Bien{len(self.biens)+1}",
                    "prix": float(entries["prix"].get() or 0),
                    "emprunt": float(entries["emprunt"].get() or 0),
                    "duree": int(float(entries["duree"].get() or 0)),
                    "taux": float(entries["taux"].get() or 0) / 100.0,
                    "loyer": float(entries["loyer"].get() or 0),
                    "charges": {
                        "assurance": float(entries["assurance"].get() or 0),
                        "taxe_fonciere": float(entries["taxe_fonciere"].get() or 0),
                        "copro": float(entries["copro"].get() or 0),
                        "assurance_emprunteur": float(entries["assurance_emprunteur"].get() or 0),
                        "autres": float(entries["autres"].get() or 0),
                    }
                }
                bien["mensualite"] = mensualite_credit(bien["emprunt"], bien["taux"], bien["duree"])
                bien["amort"] = tableau_amortissement(bien["emprunt"], bien["taux"], bien["duree"])
                self.biens.append(bien)
                self.refresh_biens_list()
                self.status.config(text=f"{bien['nom']} ajouté.")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", f"Entrées invalides : {e}")

        ttk.Button(win, text="Enregistrer le bien", command=save).grid(row=len(labels), column=0, columnspan=2, pady=12)

    def refresh_biens_list(self):
        for it in self.tree_biens.get_children():
            self.tree_biens.delete(it)
        for b in self.biens:
            self.tree_biens.insert("", "end", values=(
                b["nom"], f"{b['emprunt']:.0f}", b["duree"], f"{b['taux']*100:.2f}%",
                f"{b['loyer']:.0f}", f"{b['mensualite']:.2f}"
            ))

    # -------- Amortissement --------

    def show_amortissement_dialog(self):
        if not self.biens:
            messagebox.showwarning("Attention", "Aucun bien disponible.")
            return
        win = tk.Toplevel(self)
        win.title("Choisir un bien pour afficher l'amortissement")
        win.geometry("380x140")

        ttk.Label(win, text="Bien :").pack(pady=8)
        noms = [b["nom"] for b in self.biens]
        var = tk.StringVar(value=noms[0])
        cb = ttk.Combobox(win, textvariable=var, values=noms, state="readonly")
        cb.pack(pady=4)

        def open_for():
            name = var.get()
            for b in self.biens:
                if b["nom"] == name:
                    self.show_amortissement(b)
                    break
            win.destroy()

        ttk.Button(win, text="Afficher", command=open_for).pack(pady=10)

    def show_amortissement(self, bien):
        df = bien.get("amort")
        if df is None or df.empty:
            messagebox.showerror("Erreur", "Pas de données d'amortissement.")
            return
        win = tk.Toplevel(self)
        win.title(f"Amortissement — {bien['nom']}")
        win.geometry("1000x700")

        cols = ["year","month","payment","interest","principal","balance"]
        tree = ttk.Treeview(win, columns=cols, show="headings", height=26)
        headers = {
            "year":"Année","month":"Mois","payment":"Mensualité",
            "interest":"Intérêts","principal":"Capital","balance":"CRD"
        }
        for c in cols:
            tree.heading(c, text=headers[c])
            tree.column(c, anchor="center", width=140)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        for _, row in df.iterrows():
            tree.insert("", "end", values=(
                int(row["year"]), int(row["month"]),
                round(row["payment"],2), round(row["interest"],2),
                round(row["principal"],2), round(row["balance"],2)
            ))

        def export_df():
            path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
            if not path: return
            if path.lower().endswith(".csv"):
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(path, index=False)
            messagebox.showinfo("Export", f"Fichier sauvegardé :\n{path}")

        ttk.Button(win, text="Exporter (Excel/CSV)", command=export_df).pack(pady=6)

    # -------- Projection / Synthèse --------

    def _project_with_scenario(self, hyp):
        annees = list(range(1, int(hyp.duree_projection) + 1))
        resultats_cashflow = {b["nom"]: [] for b in self.biens}
        resultats_imposable = {b["nom"]: [] for b in self.biens}
        total_cashflow = np.zeros(len(annees))
        total_imposable = np.zeros(len(annees))

        for b in self.biens:
            df_am = b["amort"]
            interets_par_an = df_am.groupby("year")["interest"].sum().to_dict() if df_am is not None else {}

            # bases (année 1)
            loy_base = b["loyer"]
            ass_base = b["charges"].get("assurance", 0.0)
            copro_base = b["charges"].get("copro", 0.0)
            taxe_base = b["charges"].get("taxe_fonciere", 0.0)
            assu_empr_base = b["charges"].get("assurance_emprunteur", 0.0)
            autres_base = b["charges"].get("autres", 0.0)

            mensualite_annuelle = b["mensualite"] * 12.0

            for year in annees:
                # Indexations distinctes
                loy = loy_base * ((1 + hyp.revalo_loyers) ** (year - 1))
                ass = ass_base * ((1 + hyp.idx_assurance) ** (year - 1))
                copro = copro_base * ((1 + hyp.idx_copro) ** (year - 1))
                taxe = taxe_base * ((1 + hyp.idx_taxe) ** (year - 1))
                assu_empr = assu_empr_base * ((1 + hyp.idx_assu_empr) ** (year - 1))
                autres = autres_base * ((1 + hyp.idx_autres) ** (year - 1))
                charges_tot = ass + copro + assu_empr + autres

                annuite = mensualite_annuelle if year <= b["duree"] else 0.0
                interets = interets_par_an.get(year, 0.0) if year <= b["duree"] else 0.0

                revenu_imposable = loy - charges_tot - taxe - interets
                resultats_imposable[b["nom"]].append(revenu_imposable)

                cashflow = loy - charges_tot - taxe - annuite
                resultats_cashflow[b["nom"]].append(cashflow)

        # Agrégations
        for i,_ in enumerate(annees):
            total_cashflow[i] = sum(resultats_cashflow[b["nom"]][i] for b in self.biens)
            total_imposable[i] = sum(resultats_imposable[b["nom"]][i] for b in self.biens)

        # Impôts & PS sur le total imposable positif
        impots = np.array([max(total_imposable[i], 0)*hyp.tmi for i in range(len(annees))])
        ps = np.array([max(total_imposable[i], 0)*hyp.ps for i in range(len(annees))])
        cf_after_tax = total_cashflow - impots - ps

        return {
            "annees": annees,
            "resultats_cashflow": resultats_cashflow,
            "resultats_imposable": resultats_imposable,
            "total_cashflow": total_cashflow,
            "total_imposable": total_imposable,
            "impots": impots,
            "ps": ps,
            "cf_after_tax": cf_after_tax,
        }

    def show_projection(self):
        if not self.biens:
            messagebox.showwarning("Attention", "Aucun bien ajouté")
            return

        hyp_sel = self.hypA if self.current_scenario.get() == "A" else self.hypB
        res_sel = self._project_with_scenario(hyp_sel)

        # Fenêtre résultats
        win = tk.Toplevel(self)
        win.title(f"Synthèse — Scénario {self.current_scenario.get()}")
        win.geometry("1500x900")

        # Graphique combiné
        fig, ax = plt.subplots(figsize=(9.5, 6.0))

        # Courbes par bien (Cashflow)
        for b in self.biens:
            ax.plot(res_sel["annees"], res_sel["resultats_cashflow"][b["nom"]], label=f"CF {b['nom']}")

        # Totaux scénario sélectionné
        ax.plot(res_sel["annees"], res_sel["total_cashflow"], label=f"TOTAL CF ({self.current_scenario.get()})", linewidth=3, linestyle="--")
        ax.plot(res_sel["annees"], res_sel["cf_after_tax"], label=f"TOTAL CF après impôt+PS ({self.current_scenario.get()})", linestyle="-.")

        # Overlay A/B des totaux si demandé
        if self.overlay_AB.get():
            other = self.hypB if hyp_sel is self.hypA else self.hypA
            res_other = self._project_with_scenario(other)
            ax.plot(res_other["annees"], res_other["total_cashflow"], label=f"TOTAL CF ({other.name})", linestyle="--")
            ax.plot(res_other["annees"], res_other["cf_after_tax"], label=f"TOTAL CF après impôt+PS ({other.name})", linestyle=":")

        ax.set_title("Projection année par année — Cashflow par bien + Totaux (Impôt + PS)")
        ax.set_xlabel("Années")
        ax.set_ylabel("€ par an")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")

        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(side="left", fill="both", expand=True, padx=8, pady=8)

        # Tableau synthèse pour le scénario sélectionné
        right = ttk.Frame(win)
        right.pack(side="right", fill="both", expand=True, padx=8, pady=8)

        colonnes = (["Année"] +
                    [f"CF {b['nom']}" for b in self.biens] + [f"TOTAL CF ({hyp_sel.name})"] +
                    [f"IMP {b['nom']}" for b in self.biens] + [f"TOTAL IMP ({hyp_sel.name})"] +
                    [f"Impôt (TMI) {hyp_sel.name}", f"PS {hyp_sel.name}", f"CF après impôt+PS {hyp_sel.name}"])

        tree = ttk.Treeview(right, columns=colonnes, show="headings", height=27)
        for c in colonnes:
            tree.heading(c, text=c)
            tree.column(c, anchor="center", width=140)
        tree.pack(fill="both", expand=True)

        df_rows = []
        for i, an in enumerate(res_sel["annees"]):
            row = [an]
            # CF par bien
            for b in self.biens:
                row.append(round(res_sel["resultats_cashflow"][b["nom"]][i], 2))
            row.append(round(res_sel["total_cashflow"][i], 2))
            # Revenu imposable par bien
            for b in self.biens:
                row.append(round(res_sel["resultats_imposable"][b["nom"]][i], 2))
            row.append(round(res_sel["total_imposable"][i], 2))
            # Impôt + PS + CF net
            row.extend([
                round(res_sel["impots"][i], 2),
                round(res_sel["ps"][i], 2),
                round(res_sel["cf_after_tax"][i], 2)
            ])
            df_rows.append(row)
            tree.insert("", "end", values=row)

        # Export (inclut les deux scénarios + amortissements)
        def export_synthese():
            path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")])
            if not path: return

            if path.lower().endswith(".csv"):
                import pandas as pd
                df = pd.DataFrame(df_rows, columns=colonnes)
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                with pd.ExcelWriter(path, engine="openpyxl") as writer:
                    # Synthèse scénario sélectionné
                    pd.DataFrame(df_rows, columns=colonnes).to_excel(writer, sheet_name=f"Synthese_{hyp_sel.name}", index=False)

                    # Ajout synthèse de l'autre scénario pour comparaison
                    other = self.hypB if hyp_sel is self.hypA else self.hypA
                    res_other = self._project_with_scenario(other)
                    colonnes_other = (["Année"] +
                                      [f"CF {b['nom']}" for b in self.biens] + [f"TOTAL CF ({other.name})"] +
                                      [f"IMP {b['nom']}" for b in self.biens] + [f"TOTAL IMP ({other.name})"] +
                                      [f"Impôt (TMI) {other.name}", f"PS {other.name}", f"CF après impôt+PS {other.name}"])
                    rows_other = []
                    for i, an in enumerate(res_other["annees"]):
                        r = [an]
                        for b in self.biens:
                            r.append(round(res_other["resultats_cashflow"][b["nom"]][i], 2))
                        r.append(round(res_other["total_cashflow"][i], 2))
                        for b in self.biens:
                            r.append(round(res_other["resultats_imposable"][b["nom"]][i], 2))
                        r.append(round(res_other["total_imposable"][i], 2))
                        r.extend([
                            round(res_other["impots"][i], 2),
                            round(res_other["ps"][i], 2),
                            round(res_other["cf_after_tax"][i], 2)
                        ])
                        rows_other.append(r)
                    pd.DataFrame(rows_other, columns=colonnes_other).to_excel(writer, sheet_name=f"Synthese_{other.name}", index=False)

                    # Onglet Hypothèses
                    hyp_df = pd.DataFrame([
                        {"Scenario":"A", **self.hypA.as_dict()},
                        {"Scenario":"B", **self.hypB.as_dict()},
                    ])
                    hyp_df.to_excel(writer, sheet_name="Hypotheses", index=False)

                    # Amortissements
                    for b in self.biens:
                        am = b.get("amort")
                        if am is not None and not am.empty:
                            am.to_excel(writer, sheet_name=f"Amort_{b['nom'][:20]}", index=False)

            messagebox.showinfo("Export", f"Fichier sauvegardé :\n{path}")

        ttk.Button(right, text="Exporter Synthèse (Excel/CSV)", command=export_synthese).pack(pady=6)

# Run
if __name__ == "__main__":
    app = ImmoApp()
    app.mainloop()
