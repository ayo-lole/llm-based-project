"""Published Paper 244 (Nguyen & Dang, ICAIN 2026) aggregate rates.

Citation: Nguyen, T. & Dang, H. Architecture-constrained UI migration.
These constants are the paper's reported figures only. Thesis execution
must never write measured rates into this module.
"""

PAPER_244_REFERENCE = {
    "b0": {
        "compile": 0.44,
        "build": 0.38,
        "runtime": 0.30,
        "mvvm": 0.09,
        "violations": 6.2,
    },
    "s1": {"compile": 0.61, "build": 0.54, "runtime": 0.47, "mvvm": 0.28, "violations": 4.6, "ssim": 0.41},
    "s2": {"compile": 0.72, "build": 0.66, "runtime": 0.58, "mvvm": 0.45, "violations": 3.1},
    "s3": {"compile": 0.79, "build": 0.74, "runtime": 0.67, "mvvm": 0.78, "violations": 1.3},
    "s4": {"compile": 0.94, "build": 0.91, "runtime": 0.85, "mvvm": 0.92, "violations": 0.4, "ssim": 0.88},
    "ablation": {
        "no_feedback_loop": {"compile": 0.79},
        "no_arch_constraint": {"mvvm": 0.47},
    },
}
