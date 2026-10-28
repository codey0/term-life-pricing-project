# Term Life Pricing Project: Complete Walkthrough

# This is how to run:
pip install -r requirements.txt
python term_life_project.py

This explains every step in `term_life_project.py` in plain English. Read it alongside the code.

## The big picture

**The problem:** A life insurer sells a 20-year term policy to a 35-year-old. It pays $100,000 if the person dies within 20 years, and nothing if they survive. What should the annual premium be, how much money must the insurer set aside along the way, and how risky is selling lots of these?

**The core idea of all actuarial work:** put a price on uncertain future events by combining
1. **Probability** (how likely is each event?),
2. **Time value of money** (a dollar later is worth less than a dollar now), and
3. **Fairness/solvency** (premiums must cover costs, and the company must stay solvent).

## Step 1: The mortality table

**What it is:** A list of q_x, the probability that a person exactly x years old dies before their next birthday.

**Why we need it:** Everything else is built on it. If your death probabilities are wrong, every price is wrong.

**How we made it:** Real insurers use published tables, but I had no internet access, so the code uses the **Gompertz-Makeham law**, a well-known formula: mortality = a constant (accident risk) + an exponentially growing term (ageing risk). It matches reality well for adults: the log-scale chart is almost a straight line, meaning mortality roughly multiplies by a fixed factor every year of age (about 10% here).

**Reading the output:** q_35 is 0.00217 (about 2 in 1,000), q_65 is 0.026, q_80 is 0.103.

**Upgrade for yourself:** replace this step with a real table (e.g. a US SSA or SOA table) loaded from CSV. Nothing else changes.

## Step 2: The life table

**What it is:** Imagine 100,000 people born on the same day.
- `l_x` = how many are still alive at age x
- `d_x` = how many die during age x, which is l_x × q_x

Each year the survivors shrink: l_{x+1} = l_x × (1 − q_x).

**Why it matters:** It turns "probability of dying this year" into "probability of surviving to a given future age", which is what we need to value a 20-year policy. The probability that a 35-year-old survives k more years is l_{35+k} / l_35.

**Built-in check:** the code confirms all d_x add up to 100,000, because everyone eventually dies.

## Step 3: Present values (APVs)

**Time value of money:** At 4% interest, $1 in one year is worth 1/1.04 = 0.9615 today. Call this v. A payment in k years is worth v^k.

We need two quantities for the 35-year-old:

**A, the death benefit APV (0.0579 per $1):** For each year k, the policy pays $1 at the end of year k+1 if the person survives k years and then dies in the next year. So the contribution is v^(k+1) × P(survive k years) × q_(35+k). Add up the 20 years.
Interpretation: you'd need about 5.8 cents today, per $1 of cover, to be expected to pay all death claims. For $100,000 that is about $5,786.

**a, the annuity-due APV (13.742):** This is the value today of $1 paid at the start of each year as long as the person is alive, for up to 20 years. It's less than 20 because of interest discounting and the chance of death ending payments. It converts "an annual premium" into "today's value of all premiums".

**Verification (important habit):** I tested my formulas against a textbook identity for whole life insurance, A = 1 − d·a, where d = i/(1+i). Both sides agree to six decimals (0.248959). That's evidence the code is right. Real actuaries always build checks like this.

## Step 4: Net premium (the equivalence principle)

**Rule:** a fair premium makes the expected value of money in equal to the expected value of money out, in today's dollars.

P × a = 100,000 × A, so **P = 100,000 × A / a = $421.05/year**.

"Net" means it covers only expected death claims, with nothing for running the business.

## Step 5: Gross premium

**Why higher:** The insurer has costs and needs profit. I assumed:
- 25% of the first-year premium (agent commission, underwriting)
- 5% of premiums in later years
- $60 per policy per year in admin costs
- 8% of each premium as profit margin

These are illustrative; real figures come from company experience.

Applying the equivalence principle again, with G as the gross premium:
G·a = 100,000·A + 0.25G + 0.05G(a−1) + 60a + 0.08G·a. Solving for G gives **$562.34/year, about $46.86/month**, which is 33.6% above the net premium. That is plausible for term life.

## Step 6: Reserves

**The problem:** the premium is level, but death risk rises as you age. Early on, you collect more than you pay out in claims. Later, you collect less than the claims cost. The early surplus is not profit; it must be held back to pay future claims.

**Reserve at time t** (prospective method) = APV of future benefits − APV of future premiums, calculated for a person now aged 35+t with 20−t years left.

**Reading the chart:** the reserve starts at $0, peaks around year 12 at about $1,800 per policy, then falls to $0 at the end of the term. This hump shape is the classic term life reserve. At the start the equivalence principle makes it exactly $0 (another sanity check), and at the end there's nothing left to cover.

**Why it matters:** reserves are a liability on the insurer's balance sheet. If a company holds too little, it may not be able to pay claims.

## Step 7: Sensitivity analysis

**Question:** what if our assumptions are wrong? I re-priced under interest rates of 2-6% and mortality at 80%, 100%, 120% and 150% of the baseline.

**Findings (gross premium):**
- Baseline: $562
- Interest falls from 4% to 2%: $597 (about +6%)
- Mortality 20% worse: $659 (about +17%)
- Mortality 50% worse: $804 (about +43%)

**Takeaway:** for this product, **mortality assumptions matter far more than interest assumptions**, because it's a short-term, low-savings product. For long-duration products like whole life or annuities, interest rates matter much more. Being able to say this is exactly the kind of insight interviewers look for.

## Step 8: Monte Carlo portfolio risk

**Idea:** the expected number of deaths is a prediction; the actual number is random. We simulate one year of claims 100,000 times for portfolios of different sizes. The number of deaths follows a Binomial(N, q_35) distribution.

| Policies | Expected claims | Variability (CV) | 99.5th percentile above expected |
|---|---|---|---|
| 100 | $21.8K | 214% | +819% |
| 1,000 | $217K | 68% | +223% |
| 10,000 | $2.17M | 21% | +61% |
| 100,000 | $21.7M | 6.8% | +18% |

**Takeaway:** this is the **law of large numbers**, the reason insurance works. With 100 policies, a single death can wipe out the year. With 100,000, results are predictable. Variability relative to expected falls roughly with 1/√N: multiply the portfolio by 100 and the CV falls about 10 times.

**Why the 99.5th percentile?** European insurance regulation (Solvency II) sets capital requirements at the 99.5% level, so this connects your project to a real regulatory standard.

## Limitations (say these before an interviewer asks)
- The mortality table is a formula, not real data.
- The expense and profit assumptions are illustrative.
- Premium is assumed to be paid annually, with benefits at the end of the year of death. Real policies pay monthly and benefits are paid at the time of death.
- No lapses (policyholders who cancel), no taxes or capital costs, no investment risk.
- The reserves are "net premium reserves", the textbook version, not the regulatory (e.g. CRVM or principle-based) version.
- Monte Carlo covers only one year of claims, and the claims are independent (no pandemic or catastrophe scenario).

## Ideas to extend it
1. Load a real mortality table and compare premiums for males and females.
2. Add lapses (e.g. 5% a year) and see how reserves and premiums change.
3. Simulate the 20-year profit distribution for a portfolio, not just one year of claims.
4. Price a whole life policy or an annuity and compare their interest-rate sensitivity.
5. Wrap it in a Streamlit app where a user enters age and term.

## Concept glossary
- **q_x:** probability of dying within a year at age x
- **l_x, d_x:** survivors and deaths in the life table
- **v:** discount factor, 1/(1+i)
- **APV:** actuarial present value, the expected value of future payments in today's dollars
- **Annuity-due:** payments at the start of each period
- **Equivalence principle:** premium APV = benefit APV (+ expenses)
- **Net vs gross premium:** without vs with expenses and profit
- **Reserve:** money held for future claims, equal to the APV of future benefits minus the APV of future premiums
- **CV:** coefficient of variation, the standard deviation divided by the mean

## Resume bullets
- Priced a 20-year, $100,000 term life policy using actuarial present values and the equivalence principle, deriving net ($421) and gross ($562) annual premiums with explicit expense and profit loadings; validated code against textbook identities.
- Built a Gompertz-Makeham mortality table and life table in Python, and computed prospective policy reserves over the policy term.
- Performed sensitivity testing across interest rate and mortality assumptions, showing premiums are about 3x more sensitive to a 20% mortality shift than to a 2-point interest rate move.
- Ran a 100,000-trial Monte Carlo simulation to quantify portfolio claim volatility and 99.5th percentile stress, demonstrating the law of large numbers.
