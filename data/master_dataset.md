# Master Dataset — Documentation

Référence complète du fichier `master_dataset.csv` (+ son équivalent `master_dataset.pkl`).
Lis ce document avant d'attaquer la phase modélisation.

---

## 1. Vue d'ensemble

| | |
|---|---|
| **Objectif du projet** | Modèle de **VaR conditionnelle au régime** sur le **DFL Brent** (Dated minus Front-Line) |
| **Cible (target)** | `DFL = Platts Dated Brent − ICE Brent L1 continuous` |
| **Économique** | Risque de base résiduel d'un trader physique qui achète une cargaison pricée en Dated et se hedge en vendant un futur ICE Brent. Cette exposition n'est **pas arbitrable instantanément** car liquider physiquement implique de chartrer, stocker, livrer — coût économique réel. Le DFL est donc une **prime de risque structurelle**, pas une anomalie de pricing. |
| **Méthodologie cible** | PCA → K-means (3-4 régimes) → XGBoost classifier (transitions) → XGBoost quantile regression (VaR_95, VaR_99) → backtest Kupiec/Christoffersen/pinball loss |
| **Fenêtre temporelle** | 2014-01-02 → 2026-05-06 (3 055 jours ouvrés ICE Brent) |
| **Granularité** | Daily (1 ligne = 1 business day ICE Brent) |
| **Format** | CSV (`master_dataset.csv`, 1.45 MB) + PKL (`master_dataset.pkl`, 1.03 MB, dtypes préservés) |
| **Politique NaN** | **Aucune imputation, aucun forward-fill.** Les gaps restent NaN, à charge du downstream (XGBoost gère nativement les NaN, K-means non — voir §5) |
| **Calendrier** | ICE Brent business calendar. Toute date où ICE Brent ne settle pas est absente du dataset |

---

## 2. Colonnes — description, formule, rôle

Le dataset contient **44 colonnes** (1 index `date` + 43 valeurs) organisées en 3 blocs :

### 2.1 Raw prices — 23 colonnes

#### Brent (7 colonnes)

| Colonne | Source | Description | Pourquoi pertinent |
|---|---|---|---|
| `brent_dated` | Platts (manuel `cr.BRED.DTD@SP@P.M`) | Assessment Platts Dated Brent BFOET, USD/bbl | **Jambe 1 du DFL.** C'est le prix de référence physique pour les cargaisons North Sea loading 10-25 jours après. Benchmark global pour le crude léger sweet. |
| `brent_l1` à `brent_l6` | ICE Brent futures continuous (manuel `fu.BI.E1.C` à `fu.BI.E6.C`) | Settlement quotidien ICE Brent, contrats M+1 à M+6, back-adjusted continuous, USD/bbl | `brent_l1` = **jambe 2 du DFL** (le futur le plus proche). `l2..l6` capturent la **forme de la courbe forward** = signal n°1 sur la tightness physique. Backwardation (L1 > L6) = marché tendu, contango (L1 < L6) = marché lourd. |

#### WTI ICE (6 colonnes)

| Colonne | Source | Description | Pourquoi pertinent |
|---|---|---|---|
| `wti_l1` à `wti_l6` | ICE WTI continuous (manuel `fu.OI.E1.C` à `fu.OI.E6.C`) | Settlement quotidien ICE WTI Light Sweet Crude, contrats M+1 à M+6, USD/bbl | Cross-product : permet `brent_wti_arb` (l'écart trans-Atlantique). Quand le WTI s'éloigne du Brent, ça signale des disruptions de flow US→Europe (production schiste US, exports Atlantic Basin). Le choix ICE (vs NYMEX) garantit **même snap time que le Brent** = comparaison propre. |

#### WTI NYMEX cross-check (1 colonne)

| Colonne | Source | Description | Pourquoi pertinent |
|---|---|---|---|
| `cl_f_close` | yfinance `CL=F` close | Settlement quotidien NYMEX WTI front-month continuous | **Cross-check de robustesse.** Correlation avec `wti_l1` ICE = 0.999956. Sert au quality report pour vérifier qu'ICE WTI suit bien NYMEX (les deux convergent à expiration mais peuvent diverger intraday). Pas utilisé directement comme feature dans le modèle. |

#### Dubai Platts (3 colonnes)

| Colonne | Source | Description | Pourquoi pertinent |
|---|---|---|---|
| `dubai_l1` à `dubai_l3` | Platts Dubai swap (manuel `fu.DB.E1.C` à `fu.DB.E3.C`) | Swap mensuel cash-settled Platts Dubai, M+1 à M+3, USD/bbl | Permet l'**EFS** (`brent_l1 - dubai_l1`). Le Brent-Dubai EFS est **l'arb le plus regardé du marché crude** : quand l'EFS s'élargit, les flux Atlantic→Asia s'inversent (acheteurs asiatiques préfèrent Dubai), changeant la demande physique Brent et donc le DFL. |

#### Gasoil ICE (2 colonnes)

| Colonne | Source | Description | Pourquoi pertinent |
|---|---|---|---|
| `gasoil_l1_usd_tonne`, `gasoil_l2_usd_tonne` | ICE Low Sulphur Gasoil (manuel `fu.ULS.E1.C`, `fu.ULS.E2.C`) | Settlement ICE LSGO M+1 et M+2, **USD/tonne** (≠ bbl) | Source du `gasoil_brent_crack`. La demande gasoil/diesel européenne est le driver principal de la marge de raffinage en NW Europe, qui se répercute sur la demande crude physique → impact direct DFL. Unité USD/tonne conservée brute, conversion en USD/bbl faite à l'usage (÷ 7.45). |

#### Macro (2 colonnes)

| Colonne | Source | Description | Pourquoi pertinent |
|---|---|---|---|
| `vix` | FRED `VIXCLS` | CBOE Volatility Index (% annualisé, vol implicite 30j S&P 500) | **Régime risk-on/risk-off cross-asset.** Le VIX > 25-30 coïncide systématiquement avec des phases de stress sur les commodities. C'est le proxy macro de **panic propagation**, pas du facteur spécifique pétrole. |
| `dxy` | FRED `DTWEXBGS` | Trade-Weighted USD Index — Broad (Fed), panier de ~26 devises incluant CNY | **Force du dollar** = driver mécanique du crude (facturé USD). NB : choix de `DTWEXBGS` plutôt que le DXY ICE classique parce qu'il inclut **le yuan** (pondération Chine = importateur #1 de crude), donc plus pertinent qu'un DXY EUR/JPY/GBP dominant. |

#### Fundamentals US (2 colonnes)

| Colonne | Source | Description | Pourquoi pertinent |
|---|---|---|---|
| `crude_stocks_us` | EIA `WCESTUS1` | US Ending Stocks of Crude Oil excl. SPR, hebdomadaire, kbbl | **Inventaire crude US** = signal n°1 historique en commodity trading. Build vs draw vs saisonnalité = signal physique direct. Aligné sur la `publication_date` (mercredi 10h30 ET pour la semaine se terminant le vendredi précédent) → zéro look-ahead bias. |
| `dist_stocks_us` | EIA `WDISTUS1` | US Ending Stocks of Distillate Fuel Oil, hebdomadaire, kbbl | **Inventaire distillats US.** Stocks bas → demande gasoil/diesel tendue → propagation via crack au crude physique. Particulièrement pertinent en hiver (heating oil) et en période de stress diesel européen. |

### 2.2 Features dérivées — 20 colonnes

#### Target

| Colonne | Formule | Rôle |
|---|---|---|
| **`DFL`** | `brent_dated − brent_l1` | **La cible.** Toute la modélisation prédit la distribution conditionnelle de `DFL` à court terme. Mean ~$0, std $2.63, extrêmes jusqu'à $36 lors des chocs physiques. |

#### Brent curve features

| Colonne | Formule | Mesure |
|---|---|---|
| `brent_l1_l2` | `brent_l1 − brent_l2` | **Prompt carry / time spread.** Le spread le plus liquide et le plus informatif. > 0 = backwardation prompt = marché tendu maintenant. |
| `brent_l1_l3` | `brent_l1 − brent_l3` | Slope sur 2 mois — moins sensible au bruit prompt, plus structurel. |
| `brent_l1_l6` | `brent_l1 − brent_l6` | **Curvature anchor.** Capture la tightness sur le front 6 mois. La combinaison (L1-L2, L1-L3, L1-L6) permet une PCA à 3 facteurs (level/slope/curvature) — décomposition classique de la courbe forward. |

#### WTI curve features

| Colonne | Formule | Mesure |
|---|---|---|
| `wti_l1_l2`, `wti_l1_l3`, `wti_l1_l6` | mirroir des Brent | Permet la **comparaison de courbes** : un régime "Brent backwardation, WTI flat" est très différent d'un régime "les deux en backwardation". Signal de divergence trans-Atlantique. |

#### Dubai curve features

| Colonne | Formule | Mesure |
|---|---|---|
| `dubai_l1_l2`, `dubai_l1_l3` | mirroir | Time spread Dubai = signal sur la tightness Middle-East / Asie. La combinaison avec le Brent calendar spread révèle les divergences East-West. |

#### Cross-products

| Colonne | Formule | Mesure |
|---|---|---|
| `brent_wti_arb` | `brent_l1 − wti_l1` | **Spread trans-Atlantique** = signal sur les flux Atlantic→US. Mean historique ~$4.55, std $2.64. Élargit quand: production US schiste élevée, exports US autorisés, ou Brent tendu sur events Europe/MENA. |
| `brent_dubai_efs` | `brent_l1 − dubai_l1` | **Brent-Dubai EFS = LE feature Asia-arbitrage.** Quand l'EFS s'élargit, l'arb s'ouvre pour des cargaisons Atlantic Basin vers l'Asie (au détriment du Dubai) → impact pull demand sur le Brent. |
| `gasoil_brent_crack` | `gasoil_l1 / 7.45 − brent_l1` | **Crack gasoil-Brent en USD/bbl.** La marge raffineur sur le gasoil européen. Stress du crack signale tightness distillats → propagation à la demande crude. Mean $17, max $95 lors du pic Russie 2022. |

#### Returns et volatilités réalisées

| Colonne | Formule | Mesure |
|---|---|---|
| `brent_l1_log_ret_1d` | `log(brent_l1[t] / brent_l1[t-1])` | Log-return quotidien du Brent L1, base des vol et des features de PCA. |
| `dfl_chg_1d` | `DFL[t] - DFL[t-1]` | Variation absolue du DFL (NB : pas un log-return car DFL peut être négatif). |
| `brent_l1_vol_20d` | rolling std des log-returns 20 jours ouvrés | **Vol réalisée mensuelle.** Feature de régime classique : vol élevée = régime "stress", vol basse = régime "calme". |
| `dfl_vol_20d` | rolling std de `dfl_chg_1d` sur 20 jours | Vol propre du DFL (lente, stable). Mesure directement la **volatilité de la cible** = un indicateur clé pour calibrer la VaR. |
| `dfl_vol_ewma` | `sqrt(EWMA(dfl_chg_1d², α=0.10))` | **Vol EWMA du DFL** (rapide, lisse, style RiskMetrics, mémoire ~9j). Réagit plus vite que la 20j aux spikes et évite l'effet fantôme. Couplée à `dfl_vol_20d`, l'écart entre les deux capte l'**accélération** de la volatilité. |

#### Macro changes

| Colonne | Formule | Mesure |
|---|---|---|
| `vix_chg_5d` | `vix[t] - vix[t-5]` | Choc de vol macro sur 1 semaine. Capture les régime shifts (spike de stress). |
| `dxy_chg_5d` | `dxy[t] - dxy[t-5]` | Choc dollar 1 semaine. Le dollar bouge plus lentement que le pétrole, mais des moves rapides (banque centrale, crisis FX) impactent directement la demande crude. |

#### Stock anomalies (saisonnières)

| Colonne | Formule | Mesure |
|---|---|---|
| `crude_stock_anomaly` | `crude_stocks_us[t] − moyenne(crude_stocks_us, même iso-week, t-5y..t-1y)` | **Écart aux stocks crude saisonniers.** Capture les déviations vs pattern historique : un build "anormal" en été (saison de demande haute) est très bullish, un draw "anormal" en hiver l'est aussi. Standard pratique commodity trading. Look-ahead-safe (utilise uniquement years strictement passés). |
| `dist_stock_anomaly` | idem sur distillats | Idem sur les distillats. Saisonnalité plus marquée (heating oil hiver) → anomaly puissant l'hiver. |

---

## 3. Cohérence — pourquoi ce dataset tient debout

### 3.1 Cross-checks de sources

Plusieurs séries ont **deux sources indépendantes** qu'on a comparées :

| Pair | Correlation | Mean abs diff | Verdict |
|---|---|---|---|
| `brent_dated` (Platts) vs `DCOILBRENTEU` (FRED-Argus) | 0.999070 | $0.10/bbl | Les deux PRA mesurent bien le même actif. Garde Platts (gold standard, ta source). |
| `wti_l1` (ICE) vs `cl_f_close` (NYMEX yfinance) | 0.999956 | $0.22/bbl | ICE WTI et NYMEX WTI convergent (par construction à l'expiration). Garde ICE (snap-aligné avec Brent). |
| `brent_l1 − wti_l1` (spread) | mean $4.55, std $2.64 | — | Range historique réaliste pour le Brent-WTI arb (3-7 USD typique). |

### 3.2 Distribution de la cible DFL — réaliste

| Statistique | Valeur | Interprétation |
|---|---|---|
| Mean | +$0.11/bbl | Très proche de zéro — pas de biais structurel (le DFL est par définition autour de zéro long-terme, modulé par la tightness physique) |
| Std | $2.63/bbl | Cohérent avec la littérature trading commo (DFL Brent évolue typiquement dans une bande ±$2/bbl en marché normal) |
| Médiane | -$0.23 | Légèrement négative = le marché passe légèrement plus de temps en contango qu'en backwardation sur 2014-2026 |
| Skewness | Positive (max +$36, min -$11) | **Fat right tail** = les events bullish physiques (war risk, OPEC cuts, Hormuz fears) sont plus extrêmes que les events bearish (overstock, demand destruction). Conséquence pour la VaR : la VaR_99 long-DFL devrait être plus large que la VaR_99 short-DFL. |

### 3.3 Les 3 régimes extrêmes capturés (parfaits pour le ML)

| Période | Type d'event | DFL extrême | Drivers |
|---|---|---|---|
| **Avril 2020** | COVID demand destruction | -$10.8 à -$10.4 | Stockage saturé, demande qui s'effondre, spot collapse plus rapide que les futures. Le pendant Brent du WTI négatif. |
| **Mars 2022** | Russie/Ukraine invasion | +$11.3 à +$18.4 | Acheteurs paient une prime physique pour les barrels non-russes (auto-sanctions, peur de défaut de cargo). |
| **Avril 2026** | Choc récent (probable événement Hormuz/MENA) | **+$21.6 à +$36.0** | Le pic le plus extrême de l'histoire récente. Dated atteint $144.42, ICE Brent L1 à $94 → gap de $50 entre prompt physique et papier. **8 jours consécutifs > +$25**, événement structurellement multi-σ. |

Ces 3 clusters de queue sont **exactement la signature d'un modèle de VaR conditionnelle bien entraîné** : il doit apprendre à élargir l'intervalle de confiance pendant ces régimes "stress" et le resserrer en régime "calme". La présence du choc 2026 (qui est dans nos data récentes) **booste massivement la pertinence du training set** pour des prédictions actuelles.

### 3.4 Date hygiene — clean

- 0 weekend, 0 doublon, 0 date future
- Gap distribution attendue : 77% gaps = 1 jour (Mon→Tue etc.), 19% = 3 jours (Fri→Mon), reste = jours fériés
- Calendrier ICE Brent — voir §5.3 pour les implications

---

## 4. Politique NaN — pourquoi pas d'imputation

Choix explicite : **les NaN restent NaN.** Aucune transformation cachée.

| Source de NaN | % cells | Raison |
|---|---|---|
| `brent_dated` 20 NaN | 0.7% | Jours fériés où Platts ne publie pas d'assessment (UK bank holidays) |
| `wti_l1` 2 NaN | 0.06% | Rares jours où ICE WTI ne settle pas |
| `cl_f_close` 73 NaN | 2.4% | Jours fériés US sans NYMEX |
| `dubai_l1..l3` 86 NaN/série | 2.8% | Jours fériés asiatiques (Singapore, Japan, Hong Kong) |
| `vix`, `dxy` ~50-100 NaN | 1.6-3.7% | Jours fériés US (FRED publie sur calendrier US) |
| `gasoil_l1..l2` 70 NaN/série | 2.3% | Calendrier ICE Gasoil + données qui s'arrêtent en jan 2026 |
| **EIA stocks** | **79.9%** | **Hebdomadaire** : valeur uniquement le mercredi (publication_date). Reste = NaN. |
| `crude_stock_anomaly`, `dist_stock_anomaly` | 85% | Limité par les stocks + 5 premières années sans baseline saisonnière |

**Implications pour la modélisation** :
- **XGBoost** : gère nativement les NaN (split direction learned per node). Aucune action requise.
- **K-means + PCA** : ne gèrent pas les NaN. Avant la PCA, deux options :
  1. Travailler sur des log-returns/changements (qui ont moins de NaN que les niveaux)
  2. Forward-fill **dans le notebook de modélisation** explicitement (≠ dans le data layer) avec une politique documentée
- **EIA stocks** : sur le master daily, ils sont sparse (15-20% non-NaN). Pour les utiliser comme features quotidiennes il **faudra forward-fill explicitement** au moment du training (le ffill from publication_date est look-ahead-safe). Choix à faire dans le notebook.

---

## 5. Points d'attention

### 5.1 Look-ahead bias — sources et contrôles

**Le data layer est look-ahead-safe par construction :**
- Les prix quotidiens (Brent, WTI, Dubai, gasoil, VIX, DXY) sont des settlements de **fin de journée** → information disponible publiquement à la clôture du jour
- Les stocks EIA sont indexés sur `publication_date` (mercredi suivant le vendredi de référence), pas sur la date des données
- Le `crude_stock_anomaly` utilise une moyenne saisonnière **strictement passée** (`shift(1)` sur le pivot annuel)

**Mais attention dans la modélisation downstream** :
- Si tu prédis le DFL de demain en utilisant le DFL d'aujourd'hui + features d'aujourd'hui, c'est OK
- Si tu prédis le DFL d'aujourd'hui en utilisant des features d'aujourd'hui (snap times concurrents), tu peux avoir du **micro-leakage** : Platts Dubai assesse à 16:30 SGT (= 08:30 GMT) avant l'ICE Brent settle à 19:30 GMT. Sur un jour très volatil, ton Dubai value contient ~11h d'info du jour mais ton ICE Brent settle contient 19.5h. Lis ça comme : *Dubai dans le master représente le marché 11h plus tôt que Brent*.

### 5.2 Snap times — résumé

| Série | Heure de référence | Calendrier |
|---|---|---|
| ICE Brent (`brent_l*`) | **19:30 GMT** London | ICE Futures Europe |
| ICE WTI (`wti_l*`) | 19:30 GMT London | ICE Futures Europe (mêmes hours que Brent) |
| NYMEX WTI (`cl_f_close`) | 14:30 ET ≈ 18:30 GMT (hiver) | NYMEX |
| Platts Dated (`brent_dated`) | **16:30 London (Platts MOC window)** | UK business |
| Platts Dubai (`dubai_l*`) | **16:30 Singapore = 08:30 GMT** | Singapore business |
| VIX (`vix`) | 16:00 ET (US market close) | US business |
| DXY (`dxy`) | Daily Fed publication | US business |
| EIA stocks | 10:30 ET mercredi | US business |

→ Le DFL = `brent_dated(16:30 London)` − `brent_l1(19:30 London)` est calculé entre deux snaps **séparés de 3h**. C'est la convention de marché standard mais reste un bruit intraday qu'il vaut mieux connaître.

### 5.3 Calendrier ICE Brent comme master

- L'ICE Brent ne ferme **pas** sur la plupart des US holidays (4 juillet, Thanksgiving, Memorial Day, Labor Day, Presidents Day, MLK Day, Columbus Day) — donc ces jours sont **dans le master mais en NaN sur VIX/DXY/cl_f_close**.
- À l'inverse, ICE ferme sur les UK bank holidays (Good Friday, Easter Monday, May Day, Spring/Summer bank holiday, Boxing Day) — ces jours sont **absents du master**, même si le NYMEX trade.
- Bilan : ~10-15 jours/an de NaN unilatéraux sur les colonnes US (VIX, DXY, cl_f_close).
- Pour la modélisation : si tu utilises VIX, soit tu acceptes les NaN, soit tu forward-fill explicitement sur ces jours (1-2 jours max, c'est saint).

### 5.4 Convergence des series futures

Les `_l1` à `_l6` sont des **continuous back-adjusted series**, pas des contrats individuels. Implications :
- Les niveaux historiques ne reflètent pas les prix réels d'un contrat à l'époque (ils sont rétro-ajustés pour éliminer le roll gap)
- Les **différences** (calendar spreads) sont en revanche **correctes** par construction
- Les **log-returns** sont aussi corrects (le back-adjust additif préserve les pourcentages)
- Pour la VaR (qui modélise des variations, pas des niveaux), c'est l'usage normal et accepté

### 5.5 Brent vs WTI vs Dubai — précision sur les unités

Toutes les colonnes de prix crude sont en **USD/bbl**, sauf :
- `gasoil_l1_usd_tonne`, `gasoil_l2_usd_tonne` : en **USD/tonne** (convention européenne)
- Conversion à appliquer si tu veux les utiliser comparativement : ÷ 7.45 pour USD/bbl

Les stocks EIA sont en **kbbl (milliers de barils)**.
VIX et DXY sont des **indices sans unité** (VIX en % vol annualisé implicite, DXY = niveau d'indice).

---

## 6. Ce qui manque — extensions possibles

Classement par ROI (effort vs gain de signal pour le modèle DFL).

### 6.1 Tier A — fort ROI (à ajouter si on veut un projet "great" au lieu de "good")

| Donnée | Source | Pourquoi |
|---|---|---|
| **ARA stocks crude** (Amsterdam-Rotterdam-Antwerp) | Vortexa, Kpler (paid) | Le **vrai signal physique NW Europe** pour le DFL. Stocks ARA bas = cargaisons Brent partent vers raffineurs européens → tightness Dated. Donnée la plus directement corrélée au DFL mais paywallée. |
| **ICE COT positioning** | ICE EOD reports (gratuit, scraping requis) | Net managed-money / open interest sur ICE Brent. Signal de positioning extrême → fat-tail unwind risk. Vrai marché ICE Brent (≠ CFTC qui couvre seulement Brent Last Day Financial). |
| **NW Europe HDD anomaly** | NOAA / ECMWF (gratuit) | Heating Degree Days Rotterdam/London vs moyenne 10y. Hiver froid → tightness distillats EU → propagation crude. Plus pertinent que le NOAA NY actuellement non-collecté. |
| **OPEC+ production / compliance** | OPEC monthly + secondary sources | Décisions production OPEC+ et taux de compliance. Pas un signal temporel rapide mais structure la baseline du DFL sur trimestres. |

### 6.2 Tier B — moyen ROI

| Donnée | Source | Pourquoi |
|---|---|---|
| **Russian/Iranian exports tracker** | Kpler, Bloomberg ship-tracking (paid) | Flux Russie-Asie, Iran-Chine en barrels/jour. Changes de régime géopolitique se voient dans ces flux. |
| **Freight rates** (TD3, TD20) | Baltic Exchange (paid) | Quand le freight monte (tankers chers), arbitrage flows se fermeent → tightness régionalisée. Drive Brent-Dubai EFS et Brent-WTI arb. |
| **China crude imports monthly** | China customs | Demande #1 mondiale. Mouvements détectent les changements de patterns asiatiques. |
| **Spot ARA gasoil / Diesel cracks Singapore** | Platts (paid) | Compléterait le `gasoil_brent_crack` avec un crack spécifique géographique. |

### 6.3 Tier C — paywallées, intéressantes mais non critiques

- **Argus Sour Crude Index** (alternative price reporting pour Dubai)
- **Real-time Singapore Dubai/Oman swaps** (granularité intraday)
- **CFTC COT BB (Brent Last Day Financial Futures)** — petit marché mais signal de spec positioning marginal

### 6.4 Tier D — Tu n'as pas besoin

- **DXY ICE** : on a déjà DTWEXBGS (broader, mieux pour commodities, voir §2.1)
- **3-2-1 crack US** (RBOB + HO + WTI) : US-centric, marginal pour DFL Brent
- **Yield curve US (DGS2, DGS10)** : déjà proxié indirectement par VIX + DXY, et le DFL est piloté par le physique pas la macro lente

---

## 7. Caveats à mentionner en interview

Un interviewer commodity sérieux te demandera *"qu'est-ce qui manque ?"* Les bonnes réponses préparées :

1. **"Pas de stocks ARA"** : *"Les stocks ARA seraient le feature avec le plus fort signal pour le DFL Brent — c'est le vrai inventaire qui pilote la tightness NW Europe. Mais c'est paywallé (Vortexa/Kpler). J'ai utilisé les stocks US comme proxy partiel, en assumant les limitations."*

2. **"Pas de positioning"** : *"L'ICE COT serait utile pour capter les fat tails liés aux extrêmes de positionnement. Je l'ai laissé en extension (ICE publie en EOD report scrappable) car l'effort de scraping ne valait pas le ROI pour un projet 6 semaines. Si je devais le faire en production je commencerais par là."*

3. **"WTI calendar spread incomplet"** : *"EIA a discontinué sa série daily NYMEX futures en avril 2024, donc j'ai pris ICE WTI L1-L6 (équivalent fonctionnel) chez ma source. Le `wti_l1_l2` couvre la période complète maintenant. Sur les versions précédentes il y avait un trou 2024-2026."*

4. **"Pas de NW Europe weather"** : *"J'ai considéré HDD Rotterdam mais ça aurait été Tier 2 — la corrélation directe HDD→DFL est faible (passe via crack distillat puis crude). Avec plus de temps c'était dans le pipeline."*

5. **"Snap-time mismatch Brent-Dubai 11h"** : *"L'EFS Brent-Dubai est calculé entre deux snap times séparés par les fuseaux horaires (Singapore 16:30 vs London 19:30). C'est la convention de marché standard mais ça injecte du bruit intraday non-EFS sur les jours volatils. Je l'ai documenté dans le quality report."*

Ces 5 phrases montrent que **tu connais ce qui manque et pourquoi.** C'est la posture senior.

---

## 8. Comment charger le dataset

```python
import pandas as pd

# Option 1 : CSV (lent mais inspectable)
df = pd.read_csv("data/master_dataset.csv", parse_dates=["date"]).set_index("date")

# Option 2 : PKL (rapide, recommandé en notebook)
df = pd.read_pickle("data/master_dataset.pkl")

# Quick sanity check
print(df.shape, df.index.min(), df.index.max())
print(df["DFL"].describe())
```

---

## 9. Pipeline de régénération

Pour rebuild le master dataset depuis zéro :

```bash
source .venv/bin/activate
python scripts/01_download_fred.py        # VIXCLS, DTWEXBGS (+ 2 backups Brent/WTI)
python scripts/02_download_yfinance.py    # CL=F cross-check
python scripts/03_download_eia.py         # WCESTUS1, WDISTUS1 (+ RCLC1/RCLC2 historiques)
python scripts/04_load_manual_brent.py    # Platts Dated + ICE Brent L1-L6 from Data_brent.xlsx
python scripts/05_load_manual_gasoil.py   # ICE Gasoil L1-L2 from Data_all_maturities.xlsx
python scripts/06_load_manual_crude.py    # ICE WTI L1-L6 + Dubai L1-L3 from Data_crude.xlsx
python scripts/08_build_master_dataset.py # → master_dataset.csv
python scripts/09_export_pkl.py           # → master_dataset.pkl
```

Le pipeline est idempotent : chaque script overwrite ses outputs, run dans n'importe quel ordre des étapes 01-06, puis 08 puis 09.
