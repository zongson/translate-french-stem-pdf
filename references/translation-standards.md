# Translation and typesetting standards

## Fidelity rules

- Translate meaning, not word order. Keep the level and tone of a university course handout.
- Do not supply answers to numbered blanks or empty solution boxes.
- Preserve all numerical values, significant figures, equation signs, subscripts, superscripts, vector notation, state symbols, and units.
- Keep variables in Latin or Greek script. Use Chinese punctuation around prose while leaving equations internally conventional.
- Preserve original equation artwork wherever possible. For short retyped inline math use the embedded math-font fallback and `<sub>` / `<sup>`, e.g. `10<sup>−3</sup>` and `Z<sup>∗</sup>`. Do not replace `−`, `ℏ`, `ϕ` or unusual source variables merely because the Chinese font lacks them. Complicated vectors and multi-level equations are best retained directly from the source.
- Preserve an apparent source error in the translated PDF unless the user asks for correction. Mention a consequential suspected error separately.

## High-risk French terminology

Choose by context; the mappings below are defaults, not blind replacements.

### Physics and thermodynamics

| French | Preferred Chinese |
|---|---|
| système thermodynamique | 热力学系统 |
| grandeur / variable / fonction d'état | 热力学量／状态变量／状态函数 |
| grandeur intensive / extensive | 强度量／广延量 |
| gaz parfait | 理想气体 |
| masse volumique | 密度 |
| densité particulaire | 粒子数密度 |
| libre parcours moyen | 平均自由程 |
| quantité de matière | 物质的量 |
| volume molaire | 摩尔体积 |
| volume massique | 比体积（比容） |
| capacité thermique | 热容 |
| capacité thermique molaire | 摩尔热容 |
| capacité thermique massique | 比热容 |
| transfert thermique | 热传递 |
| travail des forces de pression | 压力功 |
| transformation isochore / isotherme / isobare | 等容／等温／等压过程 |
| transformation adiabatique | 绝热过程 |
| thermostat | 恒温热源（按课程语境也可译恒温器） |
| phase condensée | 凝聚相 |
| diagramme de Clapeyron | 克拉佩龙图 |

Do not confuse `chaleur` (热量/热) with `température` (温度), or `capacité thermique` (热容) with `capacité thermique massique` / `chaleur massique` (比热容).

### Chemistry

| French | Preferred Chinese |
|---|---|
| quantité de matière | 物质的量 |
| concentration molaire | 物质的量浓度（可简称摩尔浓度） |
| avancement de réaction | 反应进度 |
| taux d'avancement | 反应进度率／转化率，按定义判断 |
| dosage / titrage | 测定／滴定，按实验语境判断 |
| point d'équivalence | 化学计量点／等当点，按课程用语统一 |
| espèce chimique | 化学物种 |
| réactif limitant | 限量反应物 |
| rendement | 产率 |
| équilibre chimique | 化学平衡 |
| potentiel standard | 标准电极电势（电化学语境） |

Retain phase labels `(s)`, `(l)`, `(g)`, `(aq)`, oxidation states, stereochemical descriptors, reaction arrows, and charge notation exactly.

### Quantum chemistry and continuum mechanics

| French | Preferred Chinese |
|---|---|
| orbitale atomique / fonction d'onde | 原子轨道／波函数 |
| densité de probabilité de présence | 出现概率密度（全文统一，也可采用概率密度） |
| partie radiale / angulaire | 径向部分／角向部分 |
| dégénéré / dégénérescence | 简并的／简并度 |
| état stationnaire / normalisation | 定态／归一化 |
| ion hydrogénoïde | 类氢离子 |
| charge effective / constante d'écran | 有效电荷／屏蔽常数 |
| rayon orbitalaire / polarisabilité | 轨道半径／极化率 |
| dérivée particulaire | 随体导数（也可依上下文采用物质导数） |
| accélération locale / convective | 局部加速度／对流加速度 |

Keep the source's density symbol even when it uses `μ` rather than the more familiar `ρ`. Retain source grammatical-gender labels in vocabulary boxes even if they appear mistaken; translation is not an editorial correction.

### Mathematics

| French | Preferred Chinese |
|---|---|
| ensemble de définition | 定义域 |
| application | 映射 |
| image / antécédent | 像／原像（或前像，按教材习惯统一） |
| primitive | 原函数 |
| développement limité | 有限展开；若课程明确以 Taylor 为主，可译泰勒展开 |
| suite | 数列 |
| matrice | 矩阵 |
| déterminant | 行列式 |
| noyau / image d'une application linéaire | 核／像 |
| rang | 秩 |
| valeur propre / vecteur propre | 特征值／特征向量 |
| équation différentielle | 微分方程 |
| condition nécessaire / suffisante | 必要条件／充分条件 |

## Layout and readability

- Preserve the hierarchy and colors of titles, examples, questions, and solutions where practical.
- Keep Chinese at source size and preserve heading hierarchy. Typical body text is about 9–11 pt; the builder's normal fit floor is 7 pt. Tiny source labels and equation subscripts may retain their original smaller size. Improve the sentence or available text rectangle before overriding the floor.
- Mask only the source text being replaced. Do not cover neighboring frame rules, diagrams, or formula components.
- Restore only touched long frame rules; never replay all equation strokes after replacing a grouped block.
- Prefer precise prose masks beside retained formulas. Use a grouped Chinese sentence when prose and equation fragments really need to be reflowed, with exact mathematical semantics and all connector words translated.
- Word/TeX math can extend above or below the text bbox: integral limits, exponents and fraction bars may overlap neighboring prose boxes. Inspect that region and use `mask_rects`, `text_rect` or `preserved_regions`; do not automatically add broad padding to every group.
- Translate raster diagram labels and axis titles using small overlays while retaining curves, arrows and mathematical labels. Specify rotation explicitly. A low-resolution overview is for composition; zoom only the small labels or formulas that need a readable check.
