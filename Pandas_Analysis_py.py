#!/usr/bin/env python
# coding: utf-8

# # Olist E-Commerce Data Analysis
# 
# Data cleaning, exploratory analysis, and SQL-based business insights on the Olist Brazilian e-commerce dataset.

# In[1]:


import pandas as pd
import numpy as np
import glob
import os
import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine, text


# ## 1. Load Raw Data

# In[7]:


folder_path = r"C:\Users\Dell\Downloads\olist-data\*.csv"
file_paths = glob.glob(folder_path)

tables = {}
for file in file_paths:
    name = os.path.basename(file).split('.')[0]
    tables[name] = pd.read_csv(file)
    print(f"Loaded {name}: {tables[name].shape}")


# ## 2. Initial Data Overview

# In[8]:


for name, df in tables.items():
    print(f"\n{name}  |  {df.shape[0]:,} rows x {df.shape[1]} cols")
    missing = df.isnull().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        print(f"Missing values:\n{missing}")
    print(f"Duplicate rows: {df.duplicated().sum()}")


# ## 3. Data Cleaning

# ### 3.1 Remove Duplicate Rows

# In[9]:


for name, df in tables.items():
    before = len(df)
    tables[name] = df.drop_duplicates().reset_index(drop=True)
    removed = before - len(tables[name])
    if removed:
        print(f"{name}: removed {removed} duplicate rows")


# ### 3.2 Deduplicate Geolocation by Zip Code
# 
# The geolocation table has many lat/lng entries per zip code prefix. Collapse to one representative row per zip.

# In[10]:


geo = tables["olist_geolocation_dataset"]
tables["olist_geolocation_dataset"] = (
    geo.groupby("geolocation_zip_code_prefix", as_index=False)
       .agg({
           "geolocation_lat": "mean",
           "geolocation_lng": "mean",
           "geolocation_city": "first",
           "geolocation_state": "first"
       })
)
print(f"Geolocation reduced to {len(tables['olist_geolocation_dataset']):,} unique zip codes")


# ### 3.3 Missing Values — Orders
# 
# Missing approval/delivery dates correspond to orders that never reached that stage (e.g. canceled). Convert to datetime and keep these as NaT rather than imputing.

# In[11]:


orders = tables["olist_orders_dataset"]
date_cols = ["order_purchase_timestamp", "order_approved_at",
             "order_delivered_carrier_date", "order_delivered_customer_date",
             "order_estimated_delivery_date"]
for col in date_cols:
    orders[col] = pd.to_datetime(orders[col], errors="coerce")
tables["olist_orders_dataset"] = orders


# ### 3.4 Missing Values — Reviews
# 
# A missing title/message just means the customer left no comment.

# In[12]:


reviews = tables["olist_order_reviews_dataset"]
reviews["review_comment_title"] = reviews["review_comment_title"].fillna("No Title")
reviews["review_comment_message"] = reviews["review_comment_message"].fillna("No Comment")
tables["olist_order_reviews_dataset"] = reviews


# ### 3.5 Missing Values — Products
# 
# Missing category is filled as 'unknown'. The handful of missing physical dimensions are filled with the column median.

# In[13]:


products = tables["olist_products_dataset"]
products["product_category_name"] = products["product_category_name"].fillna("unknown")

numeric_cols = ["product_name_lenght", "product_description_lenght", "product_photos_qty",
                "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"]
for col in numeric_cols:
    products[col] = products[col].fillna(products[col].median())

tables["olist_products_dataset"] = products


# ### 3.6 Post-Cleaning Verification

# In[14]:


for name, df in tables.items():
    print(f"{name}: missing={df.isnull().sum().sum()}, duplicates={df.duplicated().sum()}")


# ## 4. Load Cleaned Data into SQLite

# In[15]:


engine = create_engine("sqlite:///olist.db")
for name, df in tables.items():
    df.to_sql(name, engine, if_exists="replace", index=False)

def run_query(sql, title=""):
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    print(f"\n{title}")
    print(df.to_string(index=False))
    return df

os.makedirs("power_bi_exports", exist_ok=True)

def run_and_export(sql, title, filename):
    df = run_query(sql, title)
    df.to_csv(f"power_bi_exports/{filename}.csv", index=False)
    return df


# ## 5. Exploratory Data Analysis — Visual Snapshot

# In[16]:


orders   = tables["olist_orders_dataset"]
items    = tables["olist_order_items_dataset"]
payments = tables["olist_order_payments_dataset"]
reviews  = tables["olist_order_reviews_dataset"]
products = tables["olist_products_dataset"]
trans    = tables["product_category_name_translation"]

sns.set_theme(style="whitegrid", palette="muted")
fig, axes = plt.subplots(2, 3, figsize=(20, 11))
fig.suptitle("Olist E-Commerce — EDA Snapshot", fontsize=17, fontweight="bold", y=1.01)

status_counts = orders["order_status"].value_counts()
axes[0, 0].bar(status_counts.index, status_counts.values,
               color=sns.color_palette("tab10", len(status_counts)))
axes[0, 0].set_title("Order Status Distribution")
axes[0, 0].tick_params(axis="x", rotation=40)
for bar, val in zip(axes[0, 0].patches, status_counts.values):
    axes[0, 0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 200,
                     f"{val:,}", ha="center", va="bottom", fontsize=8)

pay_counts = payments["payment_type"].value_counts()
colors = sns.color_palette("pastel", len(pay_counts))
total = pay_counts.sum()
wedges, _ = axes[0, 1].pie(pay_counts.values, labels=None, autopct=None,
                            startangle=90, colors=colors)
legend_labels = [f"{lbl}  ({v/total*100:.1f}%)" for lbl, v in zip(pay_counts.index, pay_counts.values)]
axes[0, 1].legend(wedges, legend_labels, loc="lower center", bbox_to_anchor=(0.5, -0.18),
                   ncol=2, fontsize=8, frameon=False)
axes[0, 1].set_title("Payment Type Distribution")

review_counts = reviews["review_score"].value_counts().sort_index()
bars = axes[0, 2].bar(review_counts.index.astype(str), review_counts.values,
                       color=sns.color_palette("RdYlGn", 5))
axes[0, 2].set_title("Review Score Distribution")
axes[0, 2].set_xlabel("Score")
for bar, val in zip(bars, review_counts.values):
    axes[0, 2].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 100,
                     f"{val:,}", ha="center", va="bottom", fontsize=8)

monthly_orders = (orders.groupby(orders["order_purchase_timestamp"].dt.to_period("M"))
                        .size().reset_index(name="count"))
monthly_orders["month_str"] = monthly_orders["order_purchase_timestamp"].astype(str)
axes[1, 0].plot(monthly_orders["month_str"], monthly_orders["count"],
                 marker="o", linewidth=2, color="steelblue", markersize=4)
axes[1, 0].fill_between(monthly_orders["month_str"], monthly_orders["count"],
                         alpha=0.15, color="steelblue")
axes[1, 0].set_title("Monthly Order Volume")
axes[1, 0].set_xticks(range(0, len(monthly_orders), 3))
axes[1, 0].set_xticklabels(list(monthly_orders["month_str"])[::3], rotation=45, fontsize=8)

merged_cats = (items.merge(products[["product_id", "product_category_name"]], on="product_id")
                     .merge(trans, on="product_category_name", how="left"))
top_cats = merged_cats["product_category_name_english"].value_counts().head(10)
axes[1, 1].barh(top_cats.index[::-1], top_cats.values[::-1],
                 color=sns.color_palette("Blues_r", 10))
axes[1, 1].set_title("Top 10 Categories by Order Count")
axes[1, 1].set_xlabel("Items Sold")

price_cap = items["price"].quantile(0.99)
axes[1, 2].hist(items["price"].clip(upper=price_cap), bins=60,
                 color="darkorange", edgecolor="white", linewidth=0.4)
axes[1, 2].set_title(f"Item Price Distribution (capped at R${price_cap:.0f})")
axes[1, 2].set_xlabel("Price (BRL)")
axes[1, 2].set_ylabel("Frequency")

plt.tight_layout()
plt.savefig("olist_eda_snapshot.png", dpi=150, bbox_inches="tight")
plt.show()


# ## 6. SQL Analysis
# 
# 15 business queries, each run against the cleaned SQLite database and exported to CSV.

# ### Q1 · Monthly Revenue Trend

# In[17]:


q1 = run_and_export("""
    SELECT
        strftime('%Y-%m', o.order_purchase_timestamp)   AS month,
        COUNT(DISTINCT o.order_id)                      AS total_orders,
        ROUND(SUM(oi.price), 2)                         AS product_revenue,
        ROUND(SUM(oi.freight_value), 2)                 AS freight_revenue,
        ROUND(SUM(oi.price + oi.freight_value), 2)      AS gross_revenue
    FROM olist_orders_dataset      o
    JOIN olist_order_items_dataset oi ON o.order_id = oi.order_id
    WHERE o.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY month
    ORDER BY month;
""", "Q1 · Monthly Revenue Trend", "q1_monthly_revenue")


# ### Q2 · Top 10 Product Categories by Revenue

# In[18]:


q2 = run_and_export("""
    SELECT
        COALESCE(t.product_category_name_english,
                 p.product_category_name)          AS category,
        COUNT(oi.order_item_id)                    AS items_sold,
        ROUND(SUM(oi.price), 2)                    AS revenue,
        ROUND(AVG(oi.price), 2)                    AS avg_price,
        ROUND(AVG(oi.freight_value), 2)            AS avg_freight
    FROM olist_order_items_dataset                 oi
    JOIN olist_products_dataset                    p  ON oi.product_id = p.product_id
    LEFT JOIN product_category_name_translation    t  ON p.product_category_name = t.product_category_name
    GROUP BY category
    ORDER BY revenue DESC
    LIMIT 10;
""", "Q2 · Top 10 Product Categories by Revenue", "q2_top_categories")


# ### Q3 · Customer Lifetime Value (Top 20)

# In[19]:


q3 = run_and_export("""
    SELECT
        c.customer_unique_id,
        c.customer_state,
        COUNT(DISTINCT o.order_id)                   AS total_orders,
        ROUND(SUM(oi.price + oi.freight_value), 2)  AS lifetime_value,
        ROUND(AVG(oi.price + oi.freight_value), 2)  AS avg_order_value,
        MIN(o.order_purchase_timestamp)              AS first_order,
        MAX(o.order_purchase_timestamp)              AS last_order
    FROM olist_customers_dataset       c
    JOIN olist_orders_dataset          o  ON c.customer_id = o.customer_id
    JOIN olist_order_items_dataset     oi ON o.order_id    = oi.order_id
    GROUP BY c.customer_unique_id, c.customer_state
    ORDER BY lifetime_value DESC
    LIMIT 20;
""", "Q3 · Customer Lifetime Value (Top 20)", "q3_customer_ltv")


# ### Q4 · Seller Performance Ranking (DENSE_RANK)

# In[20]:


q4 = run_and_export("""
    SELECT
        s.seller_id,
        s.seller_state,
        COUNT(DISTINCT oi.order_id)                         AS orders_fulfilled,
        ROUND(SUM(oi.price), 2)                            AS total_revenue,
        ROUND(AVG(r.review_score), 2)                      AS avg_review_score,
        DENSE_RANK() OVER (ORDER BY SUM(oi.price) DESC)    AS revenue_rank
    FROM olist_sellers_dataset             s
    JOIN olist_order_items_dataset         oi ON s.seller_id  = oi.seller_id
    JOIN olist_orders_dataset              o  ON oi.order_id  = o.order_id
    LEFT JOIN olist_order_reviews_dataset  r  ON o.order_id   = r.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY s.seller_id, s.seller_state
    ORDER BY revenue_rank
    LIMIT 20;
""", "Q4 · Seller Performance Ranking (DENSE_RANK)", "q4_seller_ranking")


# ### Q5 · Actual vs Estimated Delivery Days by State

# In[21]:


q5 = run_and_export("""
    SELECT
        c.customer_state,
        COUNT(o.order_id)                                                                  AS delivered_orders,
        ROUND(AVG(julianday(o.order_delivered_customer_date)
                - julianday(o.order_purchase_timestamp)), 1)                               AS avg_actual_days,
        ROUND(AVG(julianday(o.order_estimated_delivery_date)
                - julianday(o.order_purchase_timestamp)), 1)                               AS avg_estimated_days,
        ROUND(AVG(julianday(o.order_estimated_delivery_date)
                - julianday(o.order_delivered_customer_date)), 1)                          AS avg_days_ahead_of_estimate
    FROM olist_orders_dataset     o
    JOIN olist_customers_dataset  c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
    GROUP BY c.customer_state
    ORDER BY avg_actual_days DESC;
""", "Q5 · Actual vs Estimated Delivery Days by State", "q5_delivery_time")


# ### Q6 · Payment Method Split & Instalment Behaviour

# In[22]:


q6 = run_and_export("""
    SELECT
        payment_type,
        COUNT(*)                                                   AS txn_count,
        ROUND(SUM(payment_value), 2)                              AS total_value,
        ROUND(AVG(payment_value), 2)                              AS avg_ticket,
        ROUND(AVG(payment_installments), 1)                       AS avg_installments,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)        AS pct_of_txns,
        ROUND(100.0 * SUM(payment_value)
              / SUM(SUM(payment_value)) OVER (), 2)               AS pct_of_revenue
    FROM olist_order_payments_dataset
    GROUP BY payment_type
    ORDER BY total_value DESC;
""", "Q6 · Payment Method Split & Instalment Behaviour", "q6_payment_split")


# ### Q7 · Review Score Breakdown by Category

# In[23]:


q7 = run_and_export("""
    WITH category_reviews AS (
        SELECT
            COALESCE(t.product_category_name_english,
                     p.product_category_name)    AS category,
            r.review_score
        FROM olist_order_items_dataset             oi
        JOIN olist_products_dataset                p  ON oi.product_id  = p.product_id
        LEFT JOIN product_category_name_translation t  ON p.product_category_name = t.product_category_name
        JOIN olist_orders_dataset                  o  ON oi.order_id    = o.order_id
        JOIN olist_order_reviews_dataset           r  ON o.order_id     = r.order_id
    )
    SELECT
        category,
        COUNT(*)                                                             AS review_count,
        ROUND(AVG(review_score), 2)                                         AS avg_score,
        ROUND(100.0 * SUM(CASE WHEN review_score = 5 THEN 1 ELSE 0 END)
              / COUNT(*), 1)                                                 AS pct_5star,
        ROUND(100.0 * SUM(CASE WHEN review_score >= 4 THEN 1 ELSE 0 END)
              / COUNT(*), 1)                                                 AS pct_positive,
        ROUND(100.0 * SUM(CASE WHEN review_score <= 2 THEN 1 ELSE 0 END)
              / COUNT(*), 1)                                                 AS pct_negative
    FROM category_reviews
    GROUP BY category
    HAVING review_count > 100
    ORDER BY avg_score DESC
    LIMIT 20;
""", "Q7 · Review Score Breakdown by Category", "q7_review_by_category")


# ### Q8 · Late Delivery Rate by Seller State

# In[24]:


q8 = run_and_export("""
    SELECT
        s.seller_state,
        COUNT(DISTINCT o.order_id)                                                     AS total_orders,
        SUM(CASE
            WHEN julianday(o.order_delivered_customer_date)
               > julianday(o.order_estimated_delivery_date) THEN 1 ELSE 0
            END)                                                                        AS late_deliveries,
        ROUND(100.0 * SUM(CASE
            WHEN julianday(o.order_delivered_customer_date)
               > julianday(o.order_estimated_delivery_date) THEN 1 ELSE 0
            END) / COUNT(DISTINCT o.order_id), 2)                                      AS late_pct,
        ROUND(AVG(CASE
            WHEN julianday(o.order_delivered_customer_date)
               > julianday(o.order_estimated_delivery_date)
            THEN julianday(o.order_delivered_customer_date)
               - julianday(o.order_estimated_delivery_date)
            END), 1)                                                                    AS avg_days_overdue
    FROM olist_orders_dataset           o
    JOIN olist_order_items_dataset      oi ON o.order_id   = oi.order_id
    JOIN olist_sellers_dataset          s  ON oi.seller_id = s.seller_id
    WHERE o.order_status = 'delivered'
      AND o.order_delivered_customer_date IS NOT NULL
    GROUP BY s.seller_state
    ORDER BY late_pct DESC;
""", "Q8 · Late Delivery Rate by Seller State", "q8_late_delivery")


# ### Q9 · Month-over-Month Revenue Growth (LAG)

# In[25]:


q9 = run_and_export("""
    WITH monthly AS (
        SELECT
            strftime('%Y-%m', o.order_purchase_timestamp)  AS month,
            ROUND(SUM(oi.price + oi.freight_value), 2)     AS revenue
        FROM olist_orders_dataset      o
        JOIN olist_order_items_dataset oi ON o.order_id = oi.order_id
        WHERE o.order_status NOT IN ('canceled', 'unavailable')
        GROUP BY month
    )
    SELECT
        month,
        revenue,
        LAG(revenue)  OVER (ORDER BY month)                                           AS prev_month_revenue,
        ROUND(revenue - LAG(revenue) OVER (ORDER BY month), 2)                        AS revenue_delta,
        ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
              / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2)                     AS mom_growth_pct
    FROM monthly
    ORDER BY month;
""", "Q9 · Month-over-Month Revenue Growth (LAG)", "q9_mom_growth")


# ### Q10 · RFM Segmentation (NTILE Quintiles)

# In[26]:


q10 = run_and_export("""
    WITH rfm_raw AS (
        SELECT
            c.customer_unique_id,
            MAX(o.order_purchase_timestamp)               AS last_purchase,
            COUNT(DISTINCT o.order_id)                    AS frequency,
            ROUND(SUM(oi.price + oi.freight_value), 2)   AS monetary
        FROM olist_customers_dataset       c
        JOIN olist_orders_dataset          o  ON c.customer_id = o.customer_id
        JOIN olist_order_items_dataset     oi ON o.order_id    = oi.order_id
        WHERE o.order_status = 'delivered'
        GROUP BY c.customer_unique_id
    ),
    rfm_scored AS (
        SELECT *,
            NTILE(5) OVER (ORDER BY last_purchase DESC)  AS r_score,
            NTILE(5) OVER (ORDER BY frequency ASC)       AS f_score,
            NTILE(5) OVER (ORDER BY monetary ASC)        AS m_score
        FROM rfm_raw
    )
    SELECT
        r_score,
        f_score,
        m_score,
        r_score + f_score + m_score                      AS rfm_total,
        COUNT(*)                                          AS customer_count,
        ROUND(AVG(monetary), 2)                          AS avg_monetary,
        ROUND(AVG(frequency), 2)                         AS avg_frequency
    FROM rfm_scored
    GROUP BY r_score, f_score, m_score
    ORDER BY rfm_total DESC
    LIMIT 25;
""", "Q10 · RFM Segmentation (NTILE Quintiles)", "q10_rfm")


# ### Q11 · Cumulative Revenue Running Total

# In[27]:


q11 = run_and_export("""
    WITH monthly AS (
        SELECT
            strftime('%Y-%m', o.order_purchase_timestamp) AS month,
            ROUND(SUM(oi.price + oi.freight_value), 2)    AS revenue
        FROM olist_orders_dataset      o
        JOIN olist_order_items_dataset oi ON o.order_id = oi.order_id
        WHERE o.order_status NOT IN ('canceled', 'unavailable')
        GROUP BY month
    )
    SELECT
        month,
        revenue,
        ROUND(SUM(revenue) OVER (ORDER BY month
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2)   AS cumulative_revenue,
        ROUND(100.0 * revenue
              / SUM(revenue) OVER (), 2)                               AS monthly_share_pct
    FROM monthly
    ORDER BY month;
""", "Q11 · Cumulative Revenue Running Total", "q11_cumulative_revenue")


# ### Q12 · State Revenue Market Share + Pareto Cumulative %

# In[28]:


q12 = run_and_export("""
    SELECT
        c.customer_state,
        COUNT(DISTINCT o.order_id)                                               AS orders,
        ROUND(SUM(oi.price + oi.freight_value), 2)                              AS revenue,
        ROUND(100.0 * SUM(oi.price + oi.freight_value)
              / SUM(SUM(oi.price + oi.freight_value)) OVER (), 2)               AS revenue_share_pct,
        ROUND(SUM(SUM(oi.price + oi.freight_value)) OVER (
                ORDER BY SUM(oi.price + oi.freight_value) DESC
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
              / SUM(SUM(oi.price + oi.freight_value)) OVER () * 100, 1)         AS cumulative_share_pct
    FROM olist_orders_dataset           o
    JOIN olist_customers_dataset        c  ON o.customer_id = c.customer_id
    JOIN olist_order_items_dataset      oi ON o.order_id    = oi.order_id
    GROUP BY c.customer_state
    ORDER BY revenue DESC;
""", "Q12 · State Revenue Market Share + Pareto Cumulative %", "q12_state_market_share")


# ### Q13 · Top Product Pairs Bought Together (Co-Purchase Self-Join)

# In[29]:


q13 = run_and_export("""
    SELECT
        a.product_id        AS product_a,
        b.product_id        AS product_b,
        COUNT(*)            AS co_purchase_count
    FROM olist_order_items_dataset a
    JOIN olist_order_items_dataset b
        ON  a.order_id   = b.order_id
        AND a.product_id < b.product_id
    GROUP BY a.product_id, b.product_id
    ORDER BY co_purchase_count DESC
    LIMIT 15;
""", "Q13 · Top Product Pairs Bought Together (Co-Purchase Self-Join)", "q13_co_purchase")


# ### Q14 · Order-to-Delivery Funnel Timing by Stage (Hours)

# In[30]:


q14 = run_and_export("""
    SELECT
        c.customer_state,
        COUNT(o.order_id)                                                                       AS orders,
        ROUND(AVG((julianday(o.order_approved_at)
                 - julianday(o.order_purchase_timestamp)) * 24), 1)                             AS hrs_to_approval,
        ROUND(AVG((julianday(o.order_delivered_carrier_date)
                 - julianday(o.order_approved_at)) * 24), 1)                                    AS hrs_approval_to_carrier,
        ROUND(AVG((julianday(o.order_delivered_customer_date)
                 - julianday(o.order_delivered_carrier_date)) * 24), 1)                         AS hrs_carrier_to_customer,
        ROUND(AVG((julianday(o.order_delivered_customer_date)
                 - julianday(o.order_purchase_timestamp)) * 24), 1)                             AS hrs_total_end_to_end
    FROM olist_orders_dataset     o
    JOIN olist_customers_dataset  c ON o.customer_id = c.customer_id
    WHERE o.order_status = 'delivered'
      AND o.order_approved_at              IS NOT NULL
      AND o.order_delivered_carrier_date   IS NOT NULL
      AND o.order_delivered_customer_date  IS NOT NULL
    GROUP BY c.customer_state
    ORDER BY hrs_total_end_to_end DESC;
""", "Q14 · Order-to-Delivery Funnel Timing by Stage (Hours)", "q14_delivery_funnel")


# ### Q15 · Freight Cost as % of Product Revenue by Category (RANK)

# In[31]:


q15 = run_and_export("""
    WITH cat_freight AS (
        SELECT
            COALESCE(t.product_category_name_english,
                     p.product_category_name)      AS category,
            COUNT(oi.order_item_id)                AS items_sold,
            ROUND(SUM(oi.price), 2)                AS total_revenue,
            ROUND(SUM(oi.freight_value), 2)        AS total_freight
        FROM olist_order_items_dataset                 oi
        JOIN olist_products_dataset                    p  ON oi.product_id = p.product_id
        LEFT JOIN product_category_name_translation    t  ON p.product_category_name = t.product_category_name
        GROUP BY category
        HAVING items_sold > 30
    )
    SELECT
        category,
        items_sold,
        total_revenue,
        total_freight,
        ROUND(100.0 * total_freight / NULLIF(total_revenue, 0), 2)          AS freight_pct,
        RANK() OVER (ORDER BY total_freight / NULLIF(total_revenue, 0) DESC) AS freight_burden_rank
    FROM cat_freight
    ORDER BY freight_pct DESC
    LIMIT 15;
""", "Q15 · Freight Cost as % of Product Revenue by Category (RANK)", "q15_freight_burden")


# In[ ]:


print("All 15 queries done. CSVs saved to power_bi_exports/")

