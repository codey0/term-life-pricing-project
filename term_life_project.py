"""
TERM LIFE INSURANCE PRICING & RISK PROJECT
==========================================
A beginner-friendly actuarial project. Run it top to bottom: each STEP prints what it found.

Product we are pricing:
  * 20-year level term life policy, issued to a 35-year-old
  * Pays $100,000 at the END of the year of death if death occurs within 20 years
  * Premium is paid at the START of each year while the policyholder is alive
  * Insurer earns 4% interest on its money
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "."
OMEGA = 120                      # nobody is assumed to live past 120
FACE, ISSUE_AGE, TERM, INTEREST = 100_000, 35, 20, 0.04


# ======================================================================
# STEP 1: BUILD A MORTALITY TABLE
# ----------------------------------------------------------------------
# q_x = probability that someone aged exactly x dies before turning x+1.
# Real insurers use published tables (e.g. from the SOA). We don't have
# internet here, so we generate one from a famous formula, Gompertz-Makeham:
#     force of mortality  mu_x = A + B * c^x
#   A = accident risk that doesn't depend on age
#   B * c^x = ageing risk that grows exponentially
# Integrating mu over one year and converting to a probability gives q_x.
# `mult` lets us scale mortality up or down later (a "stress test").
# ======================================================================
def mortality_table(A=0.0007, B=0.00005, c=1.10, mult=1.0):
    ages = np.arange(0, OMEGA + 1)
    cumulative_hazard = A + B * c ** ages * (c - 1) / np.log(c)   # integral of mu over [x, x+1]
    q = 1 - np.exp(-cumulative_hazard)
    q = np.clip(q * mult, 0, 1)
    q[-1] = 1.0                                                   # everyone dies by OMEGA
    return pd.DataFrame({"age": ages, "qx": q})


# ======================================================================
# STEP 2: TURN q_x INTO A LIFE TABLE
# ----------------------------------------------------------------------
# Imagine 100,000 babies born together (the "radix").
#   l_x = how many are still alive at age x
#   d_x = how many die between x and x+1  (= l_x * q_x)
# l_{x+1} = l_x * (1 - q_x). Survival probability from x to x+k is l_{x+k}/l_x.
# ======================================================================
def life_table(tbl, radix=100_000):
    q = tbl["qx"].values
    l = radix * np.concatenate([[1.0], np.cumprod(1 - q[:-1])])
    out = tbl.copy()
    out["lx"] = l
    out["dx"] = l * q
    return out


# ======================================================================
# STEP 3: PRESENT VALUES (the heart of actuarial math)
# ----------------------------------------------------------------------
# $1 paid in k years is worth v^k today, where v = 1/(1+i).
# We need two "actuarial present values" (APVs) for someone aged x:
#
#  A = APV of $1 paid at end of year of death, if death is within n years
#      = sum over k=0..n-1 of  v^(k+1) * P(survive k years) * q_{x+k}
#      (survive k years, then die in year k+1, payment at year k+1)
#
#  a = APV of $1 paid at start of each year while alive, for up to n years
#      = sum over k=0..n-1 of  v^k * P(survive k years)
#      (called a "temporary annuity-due")
# ======================================================================
def apv_term(lt, x, n, i):
    v = 1 / (1 + i)
    k = np.arange(n)
    l, q = lt["lx"].values, lt["qx"].values
    surv = l[x + k] / l[x]
    A = np.sum(v ** (k + 1) * surv * q[x + k])
    a = np.sum(v ** k * surv)
    return A, a


# ======================================================================
# STEP 4: NET PREMIUM via the EQUIVALENCE PRINCIPLE
# ----------------------------------------------------------------------
# Fair premium: APV(premiums) = APV(benefits)  ->  P * a = FACE * A
# so P = FACE * A / a. "Net" means no expenses or profit yet.
# ======================================================================
def net_premium(lt, x, n, i, face=FACE):
    A, a = apv_term(lt, x, n, i)
    return face * A / a


# ======================================================================
# STEP 5: GROSS PREMIUM (add expenses and profit)
# ----------------------------------------------------------------------
# Real premiums must also cover costs. Assumptions (typical-looking, made up):
#   * 25% of first-year premium (agent commission + underwriting)
#   * 5% of premium in renewal years 2+
#   * $60 per policy per year (admin)
#   * 8% of every premium is kept as profit margin
# Equivalence principle again (G = gross premium):
#   G*a = FACE*A + 0.25G + 0.05G(a-1) + 60a + 0.08 G a
# Solve for G.
# ======================================================================
def gross_premium(lt, x, n, i, face=FACE, first=0.25, renewal=0.05, fixed=60, profit=0.08):
    A, a = apv_term(lt, x, n, i)
    denom = a - first - renewal * (a - 1) - profit * a
    return (face * A + fixed * a) / denom


# ======================================================================
# STEP 6: POLICY RESERVES
# ----------------------------------------------------------------------
# Level premiums are higher than the true cost of death early on and lower
# later. The extra early money must be set aside: the RESERVE.
# Prospective method: reserve at time t =
#     APV(future benefits) - APV(future net premiums), from age x+t with n-t years left.
# ======================================================================
def reserves(lt, x, n, i, face=FACE):
    P = net_premium(lt, x, n, i, face)
    out = []
    for t in range(n + 1):
        if t == n:
            out.append(0.0)
            continue
        A, a = apv_term(lt, x + t, n - t, i)
        out.append(face * A - P * a)
    return np.array(out)


# ======================================================================
# STEP 7: SENSITIVITY (what if our assumptions are wrong?)
# ----------------------------------------------------------------------
# Re-price under different interest rates and mortality levels.
# ======================================================================
def sensitivity(rates, mults):
    rows = []
    for m in mults:
        lt = life_table(mortality_table(mult=m))
        for r in rates:
            rows.append({"mortality_multiplier": m, "interest": r,
                         "gross_premium": gross_premium(lt, ISSUE_AGE, TERM, r)})
    return pd.DataFrame(rows)


# ======================================================================
# STEP 8: MONTE CARLO - HOW RISKY IS A PORTFOLIO?
# ----------------------------------------------------------------------
# Expected claims are one thing; actual claims are random. Simulate one
# year of claims for N identical 35-year-olds many times:
#   deaths ~ Binomial(N, q_35),  claims = FACE * deaths.
# Key idea (law of large numbers): bigger portfolios have more predictable
# results relative to their size. That is why insurance works.
# ======================================================================
def portfolio_risk(q, sizes, sims=100_000, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for N in sizes:
        claims = FACE * rng.binomial(N, q, sims)
        mean = claims.mean()
        rows.append({"policies": N, "expected_claims": mean,
                     "cv_pct": 100 * claims.std() / mean,
                     "p995_over_mean_pct": 100 * (np.percentile(claims, 99.5) / mean - 1)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    # ---- Steps 1-2
    tbl = mortality_table(); lt = life_table(tbl)
    lt.to_csv(f"{OUT}/life_table.csv", index=False)
    print("STEP 1-2  Mortality / life table")
    print(lt.loc[[0, 20, 35, 50, 65, 80, 100], ["age", "qx", "lx", "dx"]].round(5).to_string(index=False))
    print(f"  Check: sum of all deaths = {lt.dx.sum():,.0f} (should equal 100,000)")
    ex = (lt.lx.values[ISSUE_AGE:].sum() - lt.lx.values[ISSUE_AGE] / 2) / lt.lx.values[ISSUE_AGE]
    print(f"  Approx. remaining life expectancy at 35: {ex:.1f} years\n")

    # ---- Step 3 + verification
    A, a = apv_term(lt, ISSUE_AGE, TERM, INTEREST)
    print("STEP 3  Present values for 20-yr term at 35, i=4%")
    print(f"  A (death benefit APV per $1): {A:.6f}")
    print(f"  a (annuity-due APV):          {a:.4f}")
    # Sanity check using a textbook identity for WHOLE life: A = 1 - d*a, d = i/(1+i)
    Aw, aw = apv_term(lt, ISSUE_AGE, OMEGA - ISSUE_AGE + 1, INTEREST)
    d = INTEREST / (1 + INTEREST)
    print(f"  Verification (whole life identity A = 1 - d*a): {Aw:.6f} vs {1 - d * aw:.6f}\n")

    # ---- Steps 4-5
    P = net_premium(lt, ISSUE_AGE, TERM, INTEREST)
    G = gross_premium(lt, ISSUE_AGE, TERM, INTEREST)
    print("STEP 4-5  Premiums")
    print(f"  Net premium:   ${P:,.2f} per year")
    print(f"  Gross premium: ${G:,.2f} per year  (~${G/12:,.2f}/month)")
    print(f"  Expense & profit loading: {100*(G/P-1):.1f}% above net\n")

    # ---- Step 6
    V = reserves(lt, ISSUE_AGE, TERM, INTEREST)
    pd.DataFrame({"policy_year": np.arange(TERM + 1), "reserve": V}).to_csv(f"{OUT}/reserves.csv", index=False)
    print("STEP 6  Net premium reserves (per policy)")
    print("  " + ", ".join(f"t={t}: ${V[t]:,.0f}" for t in [0, 5, 10, 15, 19, 20]) + "\n")

    # ---- Step 7
    sens = sensitivity([0.02, 0.03, 0.04, 0.05, 0.06], [0.8, 1.0, 1.2, 1.5])
    sens.to_csv(f"{OUT}/sensitivity.csv", index=False)
    print("STEP 7  Gross premium sensitivity")
    print(sens.pivot(index="mortality_multiplier", columns="interest", values="gross_premium").round(0).to_string() + "\n")

    # ---- Step 8
    risk = portfolio_risk(tbl.qx.values[ISSUE_AGE], [100, 1_000, 10_000, 100_000])
    risk.to_csv(f"{OUT}/portfolio_risk.csv", index=False)
    print(f"STEP 8  Portfolio risk (1-year claims, q35 = {tbl.qx.values[ISSUE_AGE]:.5f})")
    print(risk.round(1).to_string(index=False) + "\n")

    # ---- Charts
    fig, ax = plt.subplots(2, 2, figsize=(12, 9))
    ax[0, 0].semilogy(lt.age, lt.qx); ax[0, 0].set(title="Mortality rate q_x (log scale)", xlabel="Age", ylabel="Probability of dying within a year")
    ax[0, 1].plot(lt.age, lt.lx); ax[0, 1].set(title="Survivors l_x out of 100,000", xlabel="Age", ylabel="Alive")
    ax[1, 0].plot(np.arange(TERM + 1), V, "o-"); ax[1, 0].set(title="Reserve per policy over time", xlabel="Policy year", ylabel="$ reserve")
    for m in [0.8, 1.0, 1.2, 1.5]:
        s = sens[sens.mortality_multiplier == m]
        ax[1, 1].plot(s.interest * 100, s.gross_premium, "o-", label=f"mortality x{m}")
    ax[1, 1].set(title="Gross premium sensitivity", xlabel="Interest rate (%)", ylabel="Annual gross premium ($)"); ax[1, 1].legend()
    plt.tight_layout(); plt.savefig(f"{OUT}/term_life_charts.png", dpi=150); plt.close()

    plt.figure(figsize=(7, 4.5))
    plt.loglog(risk.policies, risk.cv_pct, "o-")
    plt.title("Bigger portfolios are more predictable"); plt.xlabel("Number of policies"); plt.ylabel("Std dev of claims / expected claims (%)")
    plt.grid(True, which="both", alpha=.3); plt.tight_layout(); plt.savefig(f"{OUT}/diversification.png", dpi=150); plt.close()
