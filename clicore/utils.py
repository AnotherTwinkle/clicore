def safeget(l, i, d):
    try:
        return l[i]
    except IndexError:
        return d

def safegetrange(l, i, ds = []):
    x = 0
    r = []
    for j in range(i):
        try:
            r.append(l[j])
        except IndexError:
            r.append(ds[x])
            x += 1
    return r