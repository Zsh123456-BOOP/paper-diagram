"""Small native drawing probe; font files are supplied by the caller."""
import argparse
from pathlib import Path
from cell_local.scene import Scene


def make_demo(directory, font):
    fonts = {'Arial': {'regular': str(font)}}
    scene = Scene('attention-live', 1000, 600, fonts=fonts)
    scene.centered_text('Attention block', 500, 58, 34, font='Arial', name='title')
    with scene.group('input-embeddings'):
        for i in range(3):
            x, y = 58+i*14, 252-i*14
            scene.poly([(x,y),(x+100,y),(x+122,y-20),(x+22,y-20)], '#D9EDE9', '#183D46', 1.3)
            scene.poly([(x+100,y),(x+122,y-20),(x+122,y+100),(x+100,y+120)], '#86BFB5', '#183D46', 1.3)
            scene.rect(x,y,100,120,'#B9DFD7','#183D46',1.3)
        scene.centered_text('Input tokens',136,425,22,font='Arial')
    for label, y, fill in [('Q',180,'#C5DEF3'),('K',290,'#D9CFEC'),('V',400,'#F3D9B3')]:
        with scene.group(label+'-projection'):
            scene.rect(295,y,115,64,fill,'#183D46',1.3,radius=10,name=label+'-box')
            scene.centered_text(label,352.5,y+32,26,font='Arial',name=label+'-label')
        with scene.group(label+'-input-arrow'):
            scene.line([(208,302),(240,302),(240,y+32),(284,y+32)],'#183D46',1.8,arrow=True)
    with scene.group('attention-computation'):
        scene.rect(500,220,185,185,'#E9F3EF','#183D46',1.4,radius=14)
        scene.centered_text('Scaled dot-product',592.5,268,18,font='Arial')
        scene.centered_text('attention',592.5,299,23,font='Arial')
        scene.centered_text('Softmax',592.5,361,20,font='Arial')
    for label,y,target in [('Q',212,260),('K',322,312),('V',432,364)]:
        with scene.group(label+'-attention-arrow'):
            scene.line([(422,y),(460,y),(460,target),(488,target)],'#183D46',1.8,arrow=True)
    with scene.group('output-matrix'):
        for row in range(3):
            for col in range(3):
                with scene.group(f'cell-r{row+1}-c{col+1}'):
                    x,y=795+col*42,250+row*42
                    scene.rect(x,y,42,42,'#B9DFD7' if row!=col else '#9AC6EF','#183D46',1.2,name=f'face-{row}-{col}')
                    scene.centered_text(str(row*3+col+1),x+21,y+21,20,font='Arial')
        scene.centered_text('Output features',858,425,22,font='Arial')
    with scene.group('output-arrow'):
        scene.line([(696,312),(783,312)],'#183D46',1.8,arrow=True)
    with scene.group('curved-residual'):
        scene.path('M148,205 C148,116 859,116 859,235',stroke='#AA8256',sw=2,arrow=True)
        scene.centered_text('Residual route',510,125,18,font='Arial',fill='#89663F')
    scene.save(directory,source='Agent-authored native PowerPoint capability demo',
               notes='Illustrative attention diagram. Not a reconstruction benchmark.')


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--font',type=Path,required=True)
    a=p.parse_args()
    if a.output_dir.exists():
        raise SystemExit('Choose a new output directory')
    make_demo(a.output_dir,a.font)
