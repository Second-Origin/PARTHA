import { useCallback, useState } from 'react';

import imgCarbonChartRelationship from '@/assets/landing/figma/carbon-chart-relationship.svg';
import imgGroup5 from '@/assets/landing/figma/group5.svg';
import imgGroup6 from '@/assets/landing/figma/group6.svg';
import imgGroup7 from '@/assets/landing/figma/group7.svg';
import imgGuarantee from '@/assets/landing/figma/guarantee.png';
import imgIcon3 from '@/assets/landing/figma/icon3.svg';
import imgInformatics from '@/assets/landing/figma/informatics.png';
import imgPieceOfEvidence from '@/assets/landing/figma/piece-of-evidence.png';
import imgSecuredPackage from '@/assets/landing/figma/secured-package.png';

/* The capabilities carousel (Figma node 534:4423).
 *
 * The design draws six states of this block. The export flattened them into
 * one very wide strip -- the five that are not showing were parked thousands
 * of pixels to the right and simply clipped, which is why Next and Previous
 * did nothing. The layout below is the design's own markup for the visible
 * state; only the quote and the two tiles change between states, so those are
 * the props, and the arrows the design already drew are now real buttons.
 *
 * In the prototype this advances on click, not on a timer, and it wraps from
 * the last capability back to the first. */

type Capability = { name: string; quote: string; icon: string };

const CAPABILITIES: Capability[] = [
  {
    name: 'Deterministic extraction',
    quote: 'Same repo + same revision \u2192 byte-identical model. No sampling, no temperature, no drift.',
    icon: imgGroup5,
  },
  {
    name: 'Evidence backed',
    quote: 'Every claim traces to file, line, symbol. No hallucinated APIs, no fabricated call sites.',
    icon: imgPieceOfEvidence,
  },
  {
    name: 'Sealed models',
    quote: 'Content-addressed and signed. Reproducible across machines, CI, and time.',
    icon: imgSecuredPackage,
  },
  {
    name: 'Language coverage matrix',
    quote: "Explicit support tiers per language. What's implemented, limited, unassessed, or unsupported.",
    icon: imgInformatics,
  },
  {
    name: 'Relationship graph',
    quote: 'Symbols, calls, imports, ownership, and dependencies as first-class edges.',
    icon: imgCarbonChartRelationship,
  },
  {
    // The design's copy ends "guessed.s." -- the stray letter is dropped here.
    name: 'Honest about limits',
    quote: 'Dynamic dispatch, reflection, and generated code are flagged, not guessed.',
    icon: imgGuarantee,
  },
];

export function CapabilitiesCarousel({ className }: { className?: string }) {
  const [index, setIndex] = useState(0);

  const goNext = useCallback(() => setIndex((i) => (i + 1) % CAPABILITIES.length), []);
  const goPrev = useCallback(
    () => setIndex((i) => (i - 1 + CAPABILITIES.length) % CAPABILITIES.length),
    [],
  );

  const current = CAPABILITIES[index];
  const next = CAPABILITIES[(index + 1) % CAPABILITIES.length];

  return (
  <div className={className} data-node-id="534:4423" data-name="capabilities">
              <div className="absolute h-[518px] left-0 top-0 w-[1390px]" data-node-id="I534:4423;519:2177" data-name="Container">
                <div className="absolute content-stretch flex flex-col items-start left-0 pr-[273px] top-0 w-[1137px]" data-node-id="I534:4423;519:2178" data-name="Container">
                  <div className="gap-x-[12px] gap-y-[12px] grid grid-cols-[__253px_599px] grid-rows-[__253px_253px] h-[518px] relative shrink-0 w-full" data-node-id="I534:4423;519:2179" data-name="Container">
                    <div className="col-start-1 justify-self-stretch relative row-start-1 self-stretch shrink-0" data-node-id="I534:4423;519:2180" data-name="Container" />
                    <div className="bg-[var(--ln-quote)] col-start-2 content-stretch flex flex-col items-start justify-self-stretch overflow-clip p-[48px] relative rounded-[60px] row-[1/span_2] self-stretch shrink-0" data-node-id="I534:4423;519:2181" data-name="Container">
                      <div className="content-stretch flex flex-[321_0_0] flex-col gap-[16px] items-start min-h-px overflow-clip relative w-full" data-node-id="I534:4423;519:2182" data-name="Container">
                        <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="I534:4423;519:2183" data-name="Text">
                          <p className="[word-break:break-word] font-display font-bold leading-[48px] not-italic relative shrink-0 text-[#fa4d01] text-[48px] whitespace-nowrap" data-node-id="I534:4423;519:2184">
                            “
                          </p>
                        </div>
                        <div className="content-stretch flex flex-col h-[156px] items-start overflow-clip relative shrink-0 w-full" data-node-id="I534:4423;519:2185" data-name="Heading 3">
                          <p className="[word-break:break-word] font-sans font-normal font-normal leading-[33px] relative shrink-0 text-[24px] text-[var(--ln-ink)] w-[503px]" data-node-id="I534:4423;519:2186" style={{ fontVariationSettings: '"CTGR" 0, "wdth" 100' }}>
                            {current.quote}
                          </p>
                        </div>
                      </div>
                    </div>
                    <div className="col-start-1 content-stretch flex flex-col items-start justify-self-stretch overflow-clip relative rounded-[56px] row-start-2 self-stretch shrink-0" data-node-id="I534:4423;519:2187" data-name="Container">
                      <div className="bg-[var(--ln-tint-blue)] overflow-clip relative shrink-0 size-[253px]" data-node-id="I534:4423;519:2188" data-name="Image (Ali Ghodsi)">
                        <div className="absolute contents left-[31px] top-[53px]" data-node-id="I534:4423;519:2189">
                          <p className="-translate-x-1/2 [word-break:break-word] absolute font-display font-bold font-bold leading-[22.5px] left-[127px] text-[#006298] text-[20px] text-center top-[143px] w-[192px]" data-node-id="I534:4423;519:2190">
                            {current.name}
                          </p>
                          <div className="absolute contents left-[97px] top-[53px]" data-node-id="I534:4423;519:2191">
                            <div className="absolute bg-[#006298] left-[97px] rounded-[10px] size-[60px] top-[53px]" data-node-id="I534:4423;519:2192" />
                            <div className="absolute inset-[25.69%_42.69%_60.08%_43.08%]" data-node-id="I534:4423;519:2193" data-name="Group">
                              <img alt="" className="absolute block inset-0 max-w-none size-full" src={current.icon} />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="absolute flex h-[518px] items-center justify-center left-[1112px] top-0 w-[25px]" data-node-id="I534:4423;519:2196">
                  <div className="-scale-y-100 flex-none rotate-180">
                    <div className="h-[518px] relative w-[25px]" data-name="Container">
                      <div className="absolute flex h-[518px] items-center justify-center left-[-253px] right-[25px] top-0" data-node-id="I534:4423;519:2197" style={{ containerType: "size" }}>
                        <div className="-scale-x-100 flex-none h-[100cqh] w-[100cqw]">
                          <div className="relative size-full" data-name="Container">
                            <div className="absolute left-0 size-[253px] top-0" data-node-id="I534:4423;519:2198" data-name="Container" />
                            <div className="absolute left-[-265px] overflow-clip size-[518px] top-0" data-node-id="I534:4423;519:2199" data-name="Icon">
                              <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgIcon3} />
                              <div className="absolute flex inset-[38.03%_8.46%_57.53%_85.74%] items-center justify-center" data-node-id="I534:4423;519:2201" style={{ containerType: "size" }}>
                                <div className="flex-none h-[100cqw] rotate-90 w-[100cqh]">
                                  <div className="relative size-full" data-name="Group">
                                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgGroup6} />
                                  </div>
                                </div>
                              </div>
                              <div className="absolute flex inset-[89%_84.94%_6.56%_9.27%] items-center justify-center" data-node-id="I534:4423;519:2204" style={{ containerType: "size" }}>
                                <div className="-rotate-90 flex-none h-[100cqw] w-[100cqh]">
                                  <div className="relative size-full" data-name="Group">
                                    <img alt="" className="absolute block inset-0 max-w-none size-full" src={imgGroup7} />
                                  </div>
                                </div>
                              </div>
                              <p className="[word-break:break-word] absolute font-display font-medium font-medium inset-[38.22%_34.94%_57.72%_53.67%] leading-[25px] text-[24px] text-white tracking-[-0.9px]" data-node-id="I534:4423;519:2369">
                                Next
                              </p>
                              <p className="[word-break:break-word] absolute font-display font-medium font-medium inset-[89%_56.37%_6.95%_24.52%] leading-[25px] text-[24px] text-white tracking-[-0.9px]" data-node-id="I534:4423;519:2371">
                                Previous
                              </p>
                            </div>
                            <div className="absolute bg-[var(--ln-grey)] content-stretch flex flex-col items-start left-0 overflow-clip rounded-[56px] size-[253px] top-[265px]" data-node-id="I534:4423;519:2213" data-name="Container">
                              <div className="overflow-clip relative shrink-0 size-[253px]" data-node-id="I534:4423;519:2214" data-name="Image (Doug Rodermund)">
                                <div className="absolute contents left-[31px] top-[53px]" data-node-id="I534:4423;519:2215">
                                  <p className="-translate-x-1/2 [word-break:break-word] absolute font-display font-bold font-bold leading-[22.5px] left-[127px] text-[#392135] text-[20px] text-center top-[143px] w-[192px]" data-node-id="I534:4423;519:2216">
                                    {next.name}
                                  </p>
                                  <div className="absolute contents left-[97px] top-[53px]" data-node-id="I534:4423;519:2217">
                                    <div className="absolute bg-[#392135] left-[97px] rounded-[10px] size-[60px] top-[53px]" data-node-id="I534:4423;519:2218" />
                                  </div>
                                </div>
                                <div className="absolute left-[109px] size-[36px] top-[65px]" data-node-id="I534:4423;519:2219" data-name="Piece Of Evidence">
                                  <img alt="" className="absolute inset-0 max-w-none object-contain pointer-events-none size-full" src={next.icon} />
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              
              
              
              
              
              </div>
              <div className="absolute bg-white border border-[#fa4d01] border-solid content-stretch flex flex-col items-start left-0 overflow-clip p-[24px] rounded-[40px] size-[253px] top-0" data-node-id="I534:4423;519:2285" data-name="Container">
                <div className="content-stretch flex flex-col h-[85.961px] items-start justify-end relative shrink-0 w-full" data-node-id="I534:4423;519:2286" data-name="Container">
                  <div className="content-stretch flex flex-[63.563_0_0] flex-col items-start min-h-px relative w-full" data-node-id="I534:4423;519:2287" data-name="Container">
                    <div className="content-stretch flex flex-col items-start relative shrink-0 w-full" data-node-id="I534:4423;519:2288" data-name="Text">
                      <p className="[word-break:break-word] font-display font-normal leading-[31.78px] not-italic relative shrink-0 text-[#312e2e] text-[31.78px] tracking-[-1.2712px] w-[202px]" data-node-id="I534:4423;519:2289">
                        Trusted by builders
                      </p>
                    </div>
                  </div>
                  <div className="h-[480px] relative shrink-0 w-full" data-node-id="I534:4423;519:2290" data-name="Text" />
                </div>
              </div>
              <div className="[word-break:break-word] absolute contents leading-[25px] left-[24px] text-[#392135] top-[40px] tracking-[-0.9px]" data-node-id="I534:4423;519:2291">
                <p className="absolute font-display font-medium font-medium left-[24px] text-[24px] top-[82px] w-[188px]" data-node-id="I534:4423;519:2292">
                  Built to be trusted by the people reading the diff.
                </p>
                <p className="absolute font-display font-light font-light left-[24px] text-[32px] top-[40px] w-[188px]" data-node-id="I534:4423;519:2293">
                  Capabilities
                </p>
              </div>
              {/* The design's Next and Previous are the two orange blocks of the
          pinwheel. Their artwork is drawn deep inside a stack of Figma flip
          transforms, so the controls live here instead, over the blocks
          themselves, where the geometry is plain. */}
      <button
        type="button"
        aria-label="Next capability"
        onClick={goNext}
        className="absolute cursor-pointer rounded-[56px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        style={{ left: 1137, top: 0, width: 253, height: 253 }}
      />
      <button
        type="button"
        aria-label="Previous capability"
        onClick={goPrev}
        className="absolute cursor-pointer rounded-[56px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
        style={{ left: 872, top: 265, width: 253, height: 253 }}
      />
    </div>
  );
}
