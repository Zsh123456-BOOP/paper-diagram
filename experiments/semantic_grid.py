"""Build a reviewed matrix as named planes, palette groups and editable cells.

The caller supplies dimensions, a palette and color indices. This helper does
not infer matrix values or use bitmap contours. All geometry is deterministic.
"""
import math
import xml.etree.ElementTree as E

SVG = 'http://www.w3.org/2000/svg'


def matrix_plane(parent, *, name, origin, u, v, values, palette,
                 background='#eeeeee', border='#999999', inset=.12):
    rows = len(values)
    cols = len(values[0]) if rows else 0
    if not rows or not cols or any(len(row) != cols for row in values):
        raise ValueError('A nonempty rectangular color-index matrix is required')
    if not 0 <= inset < .5:
        raise ValueError('Inset must be in [0, .5)')
    if any(not isinstance(i, int) or i < 0 or i >= len(palette) for row in values for i in row):
        raise ValueError('Every cell must reference a palette entry')
    if not all(len(p) == 2 and all(math.isfinite(a) for a in p) for p in (origin, u, v)):
        raise ValueError('Plane vectors must contain finite coordinates')
    if abs(u[0]*v[1]-u[1]*v[0]) < 1e-8:
        raise ValueError('Plane vectors must span a nonzero area')
    def point(a, b):
        return [origin[j]+a*u[j]+b*v[j] for j in (0, 1)]
    def polygon(holder, eid, corners, fill, width):
        return E.SubElement(holder, '{'+SVG+'}polygon', id=eid,
            points=' '.join(f'{x:.4f},{y:.4f}' for x, y in corners),
            fill=fill, stroke=border, **{'stroke-width':str(width), 'stroke-linejoin':'round'})
    plane = E.SubElement(parent, '{'+SVG+'}g', id=name, **{'data-kind':'matrix-plane'})
    polygon(plane, name+'-background', [point(0,0),point(1,0),point(1,1),point(0,1)], background, .9)
    groups = {}
    for r, row in enumerate(values):
        for c, index in enumerate(row):
            if index not in groups:
                groups[index] = E.SubElement(plane, '{'+SVG+'}g',
                    id=f'{name}-color-{index:02d}', **{'data-color':palette[index]})
            corners=[point((c+inset)/cols,(r+inset)/rows),
                     point((c+1-inset)/cols,(r+inset)/rows),
                     point((c+1-inset)/cols,(r+1-inset)/rows),
                     point((c+inset)/cols,(r+1-inset)/rows)]
            cell = polygon(groups[index], f'{name}-r{r+1:02d}-c{c+1:02d}', corners, palette[index], .55)
            cell.set('data-row',str(r+1));cell.set('data-col',str(c+1))
    return plane
