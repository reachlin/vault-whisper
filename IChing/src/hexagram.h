#pragma once
#include <stdint.h>

// Trigram bit values (3-bit, bit0=bottom line, 1=yang 0=yin):
// Qian=7 Kun=0 Zhen=1 Kan=2 Gen=4 Xun=6 Li=5 Dui=3
//
// Hexagram bits = lower_trigram | (upper_trigram << 3), stored in 6 bits.
// King Wen sequence, index 1..64.

struct HexData {
    uint8_t     bits;     // 6-bit line pattern (bit0=line1 bottom, 1=yang)
    const char* zh;       // Chinese name
    const char* en;       // English name
    const char* primary;  // ~55 char reading for primary position
    const char* relating; // ~55 char reading for relating (outcome) position
};

// bits[i] = line pattern for hexagram i (1-indexed, [0] unused)
static const HexData HEXDB[65] = {
    {0,    "",     "",              "",                                      ""},
    {0x3F, "乾",  "Heaven",        "Creative force. Act with full strength.",   "Sustain what you built. Persevere."},
    {0x00, "坤",  "Earth",         "Receptive. Yield and support others.",      "The quiet path leads to lasting gain."},
    {0x11, "屯",  "Sprouting",     "Difficult birth. Seek help; do not rush.",  "Structure emerges from early chaos."},
    {0x22, "蒙",  "Youthful Folly","Find a teacher. Accept guidance humbly.",   "Learning deepens; wisdom takes root."},
    {0x17, "需",  "Waiting",       "Nourishment comes. Wait with confidence.",  "Patient strength wins what haste loses."},
    {0x3A, "讼",  "Conflict",      "Dispute ahead. Seek mediation early.",      "Resolution favors those who step back."},
    {0x02, "师",  "The Army",      "Discipline wins. A wise leader is needed.", "Order brings lasting victory."},
    {0x10, "比",  "Union",         "Unite sincerely around common purpose.",    "Bonds formed now endure the journey."},
    {0x37, "小畜","Small Taming",  "Restrain for now. Small steps accumulate.", "Patience earns the breakthrough ahead."},
    {0x3B, "履",  "Treading",      "Walk carefully near danger. Stay aware.",   "Mindful steps pass safely through."},
    {0x07, "泰",  "Peace",         "Heaven and earth align. Great harmony.",    "Prosperity flows; share generously."},
    {0x38, "否",  "Standstill",    "Stagnation. Retreat; do not force movement.","The blocked path will open in time."},
    {0x3D, "同人","Fellowship",    "Shared vision opens every door together.",  "Community built now outlasts the work."},
    {0x2F, "大有","Great Treasure","Abundance is yours. Stay humble and share.", "Wealth wisely held grows beyond measure."},
    {0x04, "谦",  "Modesty",       "Humility brings lasting success.",          "A quiet result exceeds the boastful one."},
    {0x08, "豫",  "Enthusiasm",    "Joy mobilises others. Act from delight.",   "Energy well-aimed transforms the moment."},
    {0x19, "随",  "Following",     "Adapt to the moment. Follow what is right.","Flexibility carries you through change."},
    {0x26, "蛊",  "Decay",         "Fix neglected things. Reform with care.",   "Renewal is complete; build on firm ground."},
    {0x03, "临",  "Approach",      "Power approaches. Engage while open.",      "Stay engaged; the window may close soon."},
    {0x30, "观",  "Contemplation", "Observe before acting. Show integrity.",    "Your example speaks louder than words."},
    {0x29, "噬嗑", "Biting Through","Remove obstacles decisively. Apply justice.","Justice done clears the path forward."},
    {0x25, "贲",  "Grace",         "Adorn with substance, not surface alone.",  "Beauty and truth sustain each other."},
    {0x20, "剥",  "Splitting",     "Erosion at work. Let go of what won't hold.","What survives the stripping is real."},
    {0x01, "复",  "Return",        "The turning point. A new cycle begins.",    "Seeds of renewal grow toward the light."},
    {0x39, "无妄","Innocence",     "Act without hidden motive. Be sincere.",    "Sincerity protects against misfortune."},
    {0x27, "大畜","Great Taming",  "Hold great power in reserve. Prepare.",     "Stored strength unleashes at the right time."},
    {0x21, "颐",  "Nourishment",   "Mind what you consume: food, words, thoughts.","Nourish others; abundance returns."},
    {0x1E, "大过","Excess",        "The beam is overloaded. Bold action needed.","Extraordinary effort restores balance."},
    {0x12, "坎",  "The Abyss",     "Danger repeats. Flow through like water.",  "Consistency and trust carry you across."},
    {0x2D, "离",  "Fire",          "Cling to what gives true light. Stay clear.","Clarity maintained illuminates others."},
    {0x1C, "咸",  "Influence",     "Open feeling draws others near. Be genuine.","Mutual attraction deepens into bond."},
    {0x0E, "恒",  "Duration",      "Persist through change. Constancy endures.", "Long commitment brings its full reward."},
    {0x3C, "遁",  "Retreat",       "Withdraw skillfully. Retreat is not defeat.","Distance kept now preserves future strength."},
    {0x0F, "大壮","Great Power",   "Great force is available. Use it rightly.",  "Power well-aimed builds; misused, it breaks."},
    {0x28, "晋",  "Progress",      "Advance steadily into the light.",           "Recognition comes to those who stay true."},
    {0x05, "明夷","Darkening",     "Light is suppressed. Protect your truth.",   "Endurance through darkness yields new dawn."},
    {0x35, "家人","Family",        "Strengthen bonds at home. Lead by example.", "A well-ordered home radiates outward."},
    {0x2B, "睽",  "Opposition",    "Difference creates tension. Seek common ground.","Small agreement grows into harmony."},
    {0x14, "蹇",  "Obstruction",   "The path is blocked. Seek help; turn inward.","Obstacles faced squarely become stepping stones."},
    {0x0A, "解",  "Release",       "Tension releases. Move swiftly to resolve.", "Freedom regained; lighten what you carry."},
    {0x23, "损",  "Decrease",      "Reduce willingly. Sacrifice brings gain.",   "What you let go makes space for what matters."},
    {0x31, "益",  "Increase",      "Wind and thunder: growth accelerates now.",  "Benefit others; abundance multiplies."},
    {0x1F, "夬",  "Breakthrough",  "Decisive action breaks the deadlock.",       "Resolution demands full commitment."},
    {0x3E, "姤",  "Coming to Meet","Unexpected encounter. Discern carefully.",   "What approaches changes the situation."},
    {0x18, "萃",  "Gathering",     "People and resources converge. Lead well.",  "The gathering holds if purpose is clear."},
    {0x06, "升",  "Ascending",     "Rise steadily. Push upward with effort.",    "Continued effort carries you to the summit."},
    {0x1A, "困",  "Exhaustion",    "Trapped and drained. Hold your integrity.",  "Endurance through the trap earns freedom."},
    {0x16, "井",  "The Well",      "The source is deep. Draw with care and share.","Reliable nourishment sustains all around."},
    {0x1D, "革",  "Revolution",    "Change is inevitable. Time it well.",        "Reform completed; new order takes hold."},
    {0x2E, "鼎",  "The Cauldron",  "Transform raw material into something fine.", "Refined result nourishes and elevates."},
    {0x09, "震",  "Thunder",       "Shock awakens. Stay calm at the center.",    "After the thunder, clarity and renewal."},
    {0x24, "艮",  "Mountain",      "Keep still. Stop where stopping is right.",  "Stillness maintained opens inner vision."},
    {0x34, "渐",  "Development",   "Gradual progress. Move step by careful step.","Steady advance reaches the destination."},
    {0x0B, "归妹","Marrying Maiden","Manage expectations. Know your position.",   "Clarity of role prevents future conflict."},
    {0x0D, "丰",  "Abundance",     "Great abundance at its peak. Use it wisely.", "Share the peak; prepare for what follows."},
    {0x2C, "旅",  "The Wanderer",  "In unfamiliar territory. Stay flexible.",    "The journey itself is the teaching."},
    {0x36, "巽",  "Wind",          "Penetrate gently and persistently.",          "Gentle persistence reshapes what force cannot."},
    {0x1B, "兌",  "Joy",           "Open and joyful exchange. Communicate.",      "Joy shared deepens and spreads outward."},
    {0x32, "涣",  "Dispersion",    "Dissolve rigidity. Let barriers soften.",     "Dispersed tension reforms into new clarity."},
    {0x13, "节",  "Limitation",    "Set boundaries clearly. Discipline frees.",   "Right limits enable sustainable growth."},
    {0x33, "中孚","Inner Truth",   "Sincerity reaches even pigs and fish.",       "Authentic conviction persuades without force."},
    {0x0C, "小过","Small Excess",  "Small over-step allowed. Stay close to earth.","Modest correction returns to the right path."},
    {0x15, "既济","After Completion","Task done. Guard against complacency.",      "Completion is a beginning; stay alert."},
    {0x2A, "未济","Before Completion","Not yet done. Almost there; keep focus.",   "The final crossing requires full attention."},
};

// Reverse map: bits (0..63) → hexagram number (1..64). 0 = not found (shouldn't happen).
// Built at runtime in setup() to avoid 64-byte PROGMEM lookup cost.
static uint8_t BITS_TO_NUM[64]; // populated by hexBuildIndex()

inline void hexBuildIndex() {
    for (int i = 1; i <= 64; i++)
        BITS_TO_NUM[HEXDB[i].bits & 0x3F] = (uint8_t)i;
}

// Look up hexagram number from 6-bit line pattern. Returns 1..64.
inline uint8_t hexLookup(uint8_t bits) {
    return BITS_TO_NUM[bits & 0x3F];
}

// Flip moving lines to get relating hexagram bits.
// movingMask bit N is set if line N+1 is a moving line (old yin/yang).
inline uint8_t hexRelating(uint8_t bits, uint8_t movingMask) {
    return (bits ^ movingMask) & 0x3F;
}
