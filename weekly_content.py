"""Deterministic, themed text sets for a single 84-post campaign."""
import random

POOLS = {
    'Tiny happy faces': '˃̵ᴗ˂̵|ᵔᴗᵔ|˘ᵕ˘|◡̈|˙ᵕ˙|•ᴗ•|˃ᴗ˂|ᵕ̈|ꈍ◡ꈍ|๑•͈ᴗ•͈๑|◍•ᴗ•◍|˶ᵔ ᵕ ᵔ˶|˶ˊᜊˋ˶|˃͈◡˂͈|⌯⦁⩊⦁⌯|ⁿ.ⁿ',
    'Tiny mood faces': '>ㅅ<|⪩. .⪨|•-•|˙-˙|ᐪ ᐪ|TᴖT|•́︿•̀|ᓀ‸ᓂ|•̀-•́|°³°|˙³˙|^//^|⍢|⍤|′⧿′|ᯣ_ᯣ',
    'Little bows': '୨୧|𐙚|ꪆৎ|𝜗𝜚|ʚɞ|⪩⪨|౨ৎ|୭ৎ|𝝑୧|᧔ෆ᧓|᧔•᧓|ꔫ|୨ৎ|ʚଓ|𓊆ྀི♡𓊇ྀི|୨♡୧',
    'Little hearts': '♡|ෆ|ᥫ᭡|ᰔ|ᰔᩚ|𖹭|ღ|❥|❤︎|♡⃕|♡⃝|ꨄ︎|ᡣ𐭩|𓆩♡𓆪|ʚ♡ɞ|୨♡୧',
    'Tiny stars': '✦|✧|𖤐|⭒|⟡|⋆|⊹|✩|☆|★|✮|✴︎|☾|☀︎|𖥔|⋆｡˚',
    'Flower garden': 'ꕤ|𑁍|❀|✿|❁|⚘|𓇢𓆸|𓍯|𖥧|𖧷|☘︎|✾|✽|❃|𓆸|𖡼',
    'Sleepy little cats': 'ฅ^._.^ฅ|≽^•⩊•^≼|ᨐᵉᵒʷ|⪩. .⪨|ฅ^•-•^ฅ|/ᐠ - ˕ -マ|₍^.ꞈ.^₎⟆|≽(-⩊-マ≼|ฅ^>ω<^ฅ|˶^• ༝ •^˶|₍^._.^₎|ᓚᘏᗢ|≽^•˕•^≼|/ᐠ > ˕ <マ|₍^ ᴗ ᴗ^₎|ฅ(•⩊•)ฅ',
    'Soft bunny faces': '₍ᐢ.ˬ.ᐢ₎|꒰ᐢ. .ᐢ꒱|₍ᐢᴗ˔ᴗᐢ₎|₍ᐢ. ̫.ᐢ₎♡|₍ᐢ. ̯ .ᐢ₎|₍ᐢ− ̫ −ᐢ₎|ᘏ⑅ᘏ|ᕱ⑅ᕱ|₍ᐢ. ⩊ .ᐢ₎|ᘏ▸◂ᘏ|₍ᐢ•ﻌ•ᐢ₎|꒰ᐢ˶• ˬ •˶ᐢ꒱|₍ᐢ•ᴗ•ᐢ₎|₍ᐢ˘ᵕ˘ᐢ₎|꒰ᐢᵕᵕᐢ꒱|₍ᐢ>ᴗ<ᐢ₎',
    'Music for your bio': '♪|♬|♫|𝄞|ᕷ|♩|𝄢|♪ ˚₊|♬ ⊹|𝄞 ♡|♪ 𓂃|♬ ⋆｡˚|🎧 ♪|ıllıılıılı|♪ ⟡|♫ ୨୧',
    'Little ocean': '𓇼|𓆝|𓆟|𓆞|𓆉|𓈒|𓂃|𓏸|🐚|🫧|🌊|𓊝|☾|☀︎|𖦹|꩜',
    'Soft tiny decorations': '𓂃|𓈒|𓐍|𓏲|ꕀ|˚₊|⊹₊|༘⋆|⋆｡˚|𖥔|⟡|𓇬|ᨳ|♡|𐙚|✧',
    'Cute face collection': '˃͈◡˂͈|ꈍ◡ꈍ|๑•͈ᴗ•͈๑|◍•ᴗ•◍|˶ˊᜊˋ˶|ᓀ‸ᓂ|•́︿•̀|₍ᐢ•ﻌ•ᐢ₎|˃ 𖥦 ˂|⌯⦁⩊⦁⌯|ᵔᴗᵔ|˘ᵕ˘|˙³˙|⪩. .⪨|ʢᴗ.ᴗʡᶻ|˶ᵔ ᵕ ᵔ˶',
}


def build_posts():
    posts = []
    # Rotate themes across times of day; each day selects a different subset.
    themes = list(POOLS)
    for day in range(7):
        for slot in range(12):
            theme = themes[(slot + day * 5) % len(themes)]
            items = random.Random(f'cute-week-v1:{day}:{theme}').sample(POOLS[theme].split('|'), 12)
            body = '\n'.join('　　'.join(items[i:i + 3]) for i in range(0, 12, 3))
            text = f'{theme}\n\n{body}'
            posts.append({'theme': theme, 'text': text})
    assert len(posts) == len({p['text'] for p in posts}) == 84
    assert all(len(p['text'].encode('utf-16-le')) // 2 <= 500 for p in posts)
    return posts
