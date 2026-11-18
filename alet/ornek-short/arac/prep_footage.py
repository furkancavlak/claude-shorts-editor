"""Cut the seven shots for short-wow-1 out of the 4K trailer segments.

Every shot: exact source frames -> 9:16 crop that follows the subject (eased
keyframes on the crop centre) -> 1080x1920 30 fps H.264, timestamps from 0.
Speed rules (Furkan, 17.11): normal speed = next real frame every output frame;
slower than 1x only through motion-compensated interpolation (minterpolate);
faster than 1x by skipping real frames (never repeating one).

Run from anywhere:  py -3 prep_footage.py [shot ...]
"""
import os, subprocess, sys, math

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "assets", "v")
# read-only illustration: the trailer segments are not in this repo (placeholder path)
HAM = os.path.join(HERE, "..", "ham")
SRC = {
    "t1": os.path.join(HAM, "video-2.mp4"),   # Trailer 1, file t0 = 17.100
    "t2j": os.path.join(HAM, "video-3.mp4"),  # Trailer 2, file t0 = 136.367
    "t1d": os.path.join(HAM, "video-4.mp4"),  # Trailer 1, file t0 = 68.667
    "t2g": os.path.join(HAM, "video-5.mp4"),  # Trailer 2, file t0 = 33.200
}
T0 = {"t1": 17.100, "t2j": 136.367, "t1d": 68.667, "t2g": 33.200}
# active picture (Trailer 2 is letterboxed: cropdetect -> 3840x1728 at y=216)
ACT = {"t1": (0, 2160), "t1d": (0, 2160), "t2j": (216, 1728), "t2g": (216, 1728)}
CW = 1215  # 9:16 crop width out of a full 2160-high frame (recomputed per source below)
SUFFIX = {"pov": "pov2", "heli": "heli2", "jetski": "jetski2", "gym": "gym2"}  # v2 = letterbox removed

# name: source, first file frame, n source frames, n output frames, mode, crop centre keys [(trailer s, fraction)]
SHOTS = {
    "beach":   ("t1", 139, 46, 46, "normal", [(21.73, 0.235), (23.27, 0.265)]),
    "pov":     ("t2g", 43, 111, 111, "normal", [(34.63, 0.46), (35.60, 0.47), (36.30, 0.52), (36.90, 0.61), (37.60, 0.66), (38.33, 0.71)]),
    "airboat": ("t1", 63, 46, 56, "interp", [(19.20, 0.25), (20.70, 0.30)]),
    "heli":    ("t2j", 82, 27, 27, "normal", [(139.10, 0.70), (140.00, 0.71)]),
    "jetski":  ("t2j", 111, 53, 53, "normal", [(140.07, 0.635), (140.60, 0.61), (140.90, 0.60), (141.05, 0.59), (141.20, 0.57), (141.35, 0.52), (141.50, 0.46), (141.80, 0.43)]),
    "car":     ("t1d", 49, 70, 63, "ramp", [(70.30, 0.47), (70.65, 0.50), (70.85, 0.57), (71.05, 0.48), (71.30, 0.43), (71.50, 0.50), (71.63, 0.56), (71.95, 0.53), (72.25, 0.66), (72.60, 0.68)]),
    "gym":     ("t2g", 156, 96, 115, "interp", [(38.40, 0.52), (41.55, 0.53)]),
}


def crop_x_expr(src, first, keys, cw):
    """ffmpeg expression for crop x as a function of t (s from the shot's first frame)."""
    t_off = T0[src] + first / 30.0
    pts = [(k - t_off, c * 3840 - cw / 2) for k, c in keys]
    pts = [(t, min(max(x, 0), 3840 - cw)) for t, x in pts]
    if len(pts) == 1:
        return f"{pts[0][1]:.1f}"
    # smoothstep between keys, clamped at both ends
    expr = f"{pts[-1][1]:.1f}"
    for (ta, xa), (tb, xb) in reversed(list(zip(pts[:-1], pts[1:]))):
        d = max(tb - ta, 1e-3)
        u = f"min(max((t-({ta:.4f}))/{d:.4f},0),1)"
        seg = f"({xa:.1f}+({xb - xa:.1f})*({u})*({u})*(3-2*({u})))"
        expr = f"if(lt(t,{tb:.4f}),{seg},{expr})"
    expr = f"if(lt(t,{pts[0][0]:.4f}),{pts[0][1]:.1f},{expr})"
    return expr


def ramp_indices(n_src, n_out):
    """Real-frame speed ramp for the drift: 1x approach, surge into the broadside, 1x pass, slight push out.
    Output frame k shows source frame idx[k]; strictly increasing, so no frame ever repeats."""
    shape = []
    for k in range(n_out - 1):
        if k < 14:
            v = 1.0
        elif k < 24:
            v = 1.0 + 0.95 * math.sin(math.pi * (k - 14 + 0.5) / 10)  # surge
        elif k < 38:
            v = 1.0
        else:
            v = 1.17
        shape.append(v)
    total = sum(shape)
    scale = (n_src - 1) / total
    idx, acc = [0], 0.0
    for v in shape:
        acc += v * scale
        idx.append(int(round(acc)))
    for i in range(1, len(idx)):  # enforce strictly increasing and in range
        idx[i] = max(idx[i], idx[i - 1] + 1)
    idx = [min(i, n_src - 1) for i in idx]
    assert len(set(idx)) == len(idx), idx
    return idx


def build(name):
    src, first, n_src, n_out, mode, keys = SHOTS[name]
    y0, h = ACT[src]
    cw = int(round(h * 9 / 16 / 2)) * 2
    x = crop_x_expr(src, first, keys, cw)
    base = f"trim=start_frame={first}:end_frame={first + n_src},setpts=PTS-STARTPTS,crop=w={cw}:h={h}:x='{x}':y={y0},scale=1080:1920:flags=lanczos"
    if mode == "normal":
        vf = base + ",setpts=N/30/TB"
    elif mode == "interp":
        f = n_out / n_src
        vf = base + f",setpts=N/30/TB,setpts=PTS*{f:.6f},minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,setpts=N/30/TB"
    elif mode == "ramp":
        idx = ramp_indices(n_src, n_out)
        sel = "+".join(f"eq(n\\,{i})" for i in idx)
        vf = base + f",select='{sel}',setpts=N/30/TB"
        print(name, "ramp source frames:", idx)
    out = os.path.join(OUT, f"{SUFFIX.get(name, name)}.mp4")
    if os.path.exists(out):
        raise SystemExit(f"{out} exists; not overwriting (rename the old one by hand)")
    cmd = ["ffmpeg", "-v", "error", "-n", "-i", SRC[src], "-an", "-vf", vf, "-frames:v", str(n_out), "-r", "30",
           "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-g", "15", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    n = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                        "stream=nb_read_frames,width,height", "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
    print(f"{name}: {n} (want {n_out} frames)")


if __name__ == "__main__":
    names = sys.argv[1:] or list(SHOTS)
    for nm in names:
        build(nm)
