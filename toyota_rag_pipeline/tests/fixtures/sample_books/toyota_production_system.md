---
title: Toyota Production System Handbook
author: Reference notes compiled for the Toyota RAG project
---

# Chapter 1: Origins of the Toyota Production System

The Toyota Production System (TPS) is the management and manufacturing philosophy that Toyota developed between the late 1940s and the 1970s. It is the direct ancestor of what Western writers later called "lean manufacturing". The term "lean" itself was popularised in 1990 by the book *The Machine That Changed the World*, written by James Womack, Daniel Jones and Daniel Roos as part of MIT's International Motor Vehicle Program.

The roots of TPS reach back further than the car company. Sakichi Toyoda, the founder of the Toyoda group, was an inventor of textile looms. His Type G automatic loom, completed in 1924, could change shuttles without stopping and, crucially, stopped itself automatically when a thread broke. Because the machine stopped instead of producing defective cloth, a single operator could watch many looms at once. This idea of a machine that detects an abnormality and stops became the second pillar of TPS, known as jidoka.

Sakichi's son, Kiichiro Toyoda, led the move into automobiles in the 1930s. Kiichiro is credited with the phrase "just in time": the idea that each process should make only what is needed, when it is needed, in the amount needed. Shortages of capital and materials in post-war Japan made this idea a necessity rather than a luxury. Toyota simply could not afford the large inventories and enormous batch sizes used by American mass producers such as Ford and General Motors.

The engineer most closely associated with building TPS into a complete system is Taiichi Ohno. Ohno joined Toyoda Spinning and Weaving and moved to Toyota Motor in 1943. Working first as a machine-shop manager, he experimented for decades with pull systems, cards, small lots and multi-machine handling. He later rose to executive vice president. His book *Toyota Production System: Beyond Large-Scale Production* was published in Japanese in 1978 and in English in 1988. Ohno described the aim of the system in a single sentence: all we are doing is looking at the timeline from the moment a customer gives us an order to the point when we collect the cash, and we are reducing that timeline by removing the non-value-added wastes.

Another key contributor was Shigeo Shingo, an industrial engineer who worked with Toyota as a consultant. Shingo is best known for Single-Minute Exchange of Die (SMED), a method for cutting machine changeover times, and for poka-yoke, or mistake-proofing devices.

# Chapter 2: The House of TPS

Toyota and later writers often draw TPS as a house. The drawing is a teaching aid that shows how the elements depend on one another.

The roof of the house is the goal: the best quality, the lowest cost and the shortest lead time, together with safety and high morale. The two pillars holding up the roof are just-in-time and jidoka. The foundation is made of stability, heijunka (production levelling), standardised work and kaizen (continuous improvement). At the centre of the house are people: motivated, trained team members who solve problems every day.

The house metaphor makes one point very clearly. A company cannot copy one tool, such as kanban cards, and expect the results Toyota achieves. If the foundation of stable, levelled production is missing, just-in-time will fail because every disturbance will stop the line. If people are not trained and trusted to stop the line and solve problems, jidoka becomes a source of frustration rather than improvement.

# Chapter 3: Just-In-Time

Just-in-time (JIT) means producing and delivering exactly the right items, in the right quantity, at the right time. Three ideas sit underneath it.

## Takt time

Takt time is the pace of customer demand. It is calculated by dividing the available working time in a period by the number of units customers require in that period. For example, if a shift has 27,000 seconds of available working time and customers need 450 units per shift, the takt time is 60 seconds. Every process is designed to produce one unit roughly every 60 seconds. Producing faster than takt creates overproduction; producing slower creates shortages.

## Continuous flow

In continuous flow, parts move one piece at a time from one process step to the next, without waiting in piles between steps. Toyota rearranges equipment into cells and lines arranged in process order so that work flows. One-piece flow exposes problems quickly, because there is no inventory buffer to hide them.

## Pull systems and kanban

Where continuous flow is not possible, for example between a stamping press that must run in batches and an assembly line, Toyota uses a pull system. The downstream process withdraws what it needs from a small store called a supermarket, and the upstream process makes only enough to replace what was taken. Ohno reportedly took inspiration from American supermarkets, where shelves are restocked only as customers remove goods.

Kanban is the signalling device that controls the pull. A kanban is traditionally a card attached to a container of parts. A withdrawal kanban authorises the movement of parts from the supermarket to the user. A production kanban authorises the upstream process to make a replacement. Toyota's kanban rules include: the downstream process withdraws only what is indicated on the kanban; the upstream process produces only the quantity withdrawn; no items are made or moved without a kanban; a kanban is always attached to the goods; defective products are never sent to the next process; and reducing the number of kanbans in circulation over time exposes problems and drives improvement.

JIT depends on short changeovers. If changing a press from one die to another takes four hours, it is economically forced to run large batches. Through SMED, Toyota cut die change times on large presses from hours to under ten minutes, which made small lots practical.

# Chapter 4: Jidoka

Jidoka is often translated as "automation with a human touch" or "autonomation". It means that a machine or a process stops automatically, or is stopped by a person, as soon as an abnormality occurs. Quality is built in at the process rather than inspected in at the end.

Jidoka has four steps: detect the abnormality, stop, fix or correct the immediate condition, and investigate the root cause and install a countermeasure.

## Andon

The andon is the visual and audible signal used on Toyota assembly lines. Any team member who finds a problem pulls a cord or presses a button. A light and a tune signal the team leader, who comes to help. If the problem cannot be solved within the fixed-position cycle, the line stops. Stopping the line is not considered a failure; it is treated as an opportunity to solve a problem before it spreads.

## Poka-yoke

Poka-yoke devices are simple mechanisms that make it impossible, or immediately obvious, to make a mistake. Examples include fixtures that only accept a part in the correct orientation, sensors that count the number of bolts picked from a tray, and connectors shaped so they cannot be inserted the wrong way.

## Separating people from machines

Because machines stop themselves when something goes wrong, operators do not need to watch a single machine continuously. One person can operate several machines, which is called multi-process handling. This was the original benefit of Sakichi Toyoda's self-stopping loom.

# Chapter 5: Heijunka and Standardised Work

Heijunka means levelling production by both volume and product mix. Instead of building all of model A on Monday and all of model B on Tuesday, a levelled schedule mixes the models in a repeating sequence, such as A-B-A-C-A-B. Levelling makes demand on upstream processes and suppliers smooth and predictable, which allows small inventories and stable staffing. A heijunka box, a board with slots for kanban cards at fixed time intervals, is often used to schedule the levelled mix.

Standardised work is the documented current best method for doing a job safely and with good quality. It has three elements: takt time, the work sequence, and standard in-process stock. Standardised work is not meant to be fixed forever. Ohno argued that without a standard there can be no kaizen, because there is nothing against which to measure an improvement.

# Chapter 6: Muda, Mura and Muri

TPS identifies three enemies of efficient work.

Muda means waste: any activity that consumes resources without adding value for the customer. Mura means unevenness: fluctuations in schedule or workload. Muri means overburden: pushing people or machines beyond their natural limits. Mura often causes muri, and both create muda, so heijunka addresses the root of many wastes.

## The seven wastes

Taiichi Ohno described seven types of muda:

1. Overproduction: making more, or earlier, than the next process needs. Ohno considered this the worst waste because it hides and creates the others.
2. Waiting: people or machines idle while waiting for parts, information or a previous step.
3. Transportation: moving materials more than necessary.
4. Over-processing: doing more work than the customer requires, or using inappropriate processes.
5. Inventory: excess raw materials, work in progress or finished goods.
6. Motion: unnecessary movement by people, such as walking, reaching or searching.
7. Defects: producing parts that need rework or scrap.

Many lean practitioners add an eighth waste: unused human creativity, meaning failure to engage employees' ideas and skills.

# Chapter 7: Kaizen and Problem Solving

Kaizen means continuous improvement through many small changes, made by the people who do the work. Toyota's suggestion system historically generated very large numbers of ideas per employee, most of them small.

## The 5 Whys

The 5 Whys is a root-cause technique attributed to Sakichi Toyoda and promoted by Ohno. The investigator asks "why?" repeatedly until reaching a cause that can be fixed. Ohno's classic example concerns a machine that stopped:

- Why did the machine stop? A fuse blew because of an overload.
- Why was there an overload? The bearing was not lubricated enough.
- Why was it not lubricated enough? The lubrication pump was not pumping enough.
- Why was it not pumping enough? The pump shaft was worn and rattling.
- Why was the shaft worn? There was no strainer, so metal scrap got in.

Installing a strainer fixes the root cause; simply replacing the fuse would not.

## Genchi genbutsu

Genchi genbutsu means "go and see for yourself". Managers and engineers are expected to go to the gemba, the actual place where work happens, to observe the problem directly rather than relying on reports. The Ohno circle is a well-known training exercise in which a trainee stands in a chalk circle on the factory floor for hours, simply observing until they see the waste.

## PDCA and A3 reports

Toyota uses the Plan-Do-Check-Act cycle for structured improvement. Problems and proposals are often summarised on a single sheet of A3-size paper. An A3 report typically covers background, current condition, goal, root-cause analysis, countermeasures, implementation plan and follow-up. The discipline of fitting the thinking onto one page forces clarity.

# Chapter 8: TPS Beyond Toyota

TPS spread first to Toyota's suppliers in Japan and then worldwide. The NUMMI joint venture between Toyota and General Motors in Fremont, California, which ran from 1984 to 2010, showed that the system could work with an American workforce in a plant GM had previously closed. Toyota also set up the Toyota Production System Support Center (TSSC) in North America in 1992 to share TPS with other manufacturers and non-profit organisations.

Today lean principles derived from TPS are applied in hospitals, software development (for example kanban boards in agile teams), logistics, banking and government services.
