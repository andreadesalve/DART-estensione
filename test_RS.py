import argparse
from DART import *
from pprint import pprint
import csv
import os

# ----------------------------------------------------- 

parser = argparse.ArgumentParser(description='Esegui il test RS.')
parser.add_argument('--build', type=str,
                        default='build/contracts/DART.json',
                        help="path all'artifact DART.json prodotto da Truffle a seguito della compilazione (default: build/contracts/DART.json)")
parser.add_argument('--host', type=str,
                        default='http://localhost:8545',
                        help="hostname e porta della blockchain su cui è stato deployato DART (default: http://localhost:8545)")
parser.add_argument('--netid', type=int,
                        default=1,
                        help="network id della blockchain (default: 1)")
parser.add_argument(dest='n_eligibles', type=int, help='numero di principal da registrare come esperti')
parser.add_argument(dest='n_universities', type=int, help='numero di università da istanziare e su cui smistare gli studenti')
args = parser.parse_args()

nEligibles = args.n_eligibles
nUniversities = args.n_universities

# Inizializza web3 connettendolo al provider locale ganache
w3 = Web3(Web3.HTTPProvider(args.host))
accounts = w3.eth.accounts;
w3.eth.defaultAccount = accounts[0]

if len(accounts) < (3+nEligibles+nUniversities):
    print("Not enough available Ethereum accounts! At least (N_eligibles + N_universities + 3) accounts are needed in order to run this test")
    sys.exit(-1)

nEligiblesBuyer= nEligibles
nEligibleExpert= nEligibles//2
addressesOfEligiblesBuyer = accounts[3:3+nEligiblesBuyer]
addressesOfEligiblesExpert = accounts[3:3+nEligibleExpert]
addressesOfEligibles = accounts[3:3+nEligibles]
addressesOfUniversities = accounts[3+nEligibles:3+nEligibles+nUniversities]

# Inizializza l'interfaccia per interagire con lo smart contract DART
DARTArtifact = json.load(open(args.build))
d = DART(DARTArtifact['abi'], DARTArtifact['networks'][str(args.netid)]['address'], w3)

# ----------------------------------------------------- 

# Per facilitare la stesura dei test e la lettura dei risultati
# realizza due coppie di dizionari per legare:

# ... principals ad address e viceversa
PR = {
#   'EPapers': accounts[0],
    'Alice': accounts[0],
#    'EOrg': accounts[1],
    'RecSys': accounts[1],
    'StateA': accounts[2]
}
for idx, addr in enumerate(addressesOfEligibles):
    PR['Principal[' + str(idx+1) + ']'] = addr
for idx, addr in enumerate(addressesOfUniversities):
    PR['Uni[' + str(idx+1) + ']'] = addr
INV_PR = {v: k for k, v in PR.items()}
print("\nPRINCIPALS:")
pprint(PR)

# ... rolenames esadecimali a rolenames stringhe e viceversa
RN = {
#    'canAccess': '0x000a',
    'recommendationFrom': '0x000a',
#    'student': '0x000b',
    'reviewer': '0x000b',
#    'member': '0x000c',
    'expert': '0x000c',
#    'university': '0x000d',
    'university': '0x000d',
#   'student': '0x000e'
    'buyer': '0x000e',
    'professor': '0x000f'
}
INV_RN = {v: k for k, v in RN.items()}
print("\nROLENAMES:")
pprint(RN)


# Funzione di utilità per convertire una Expression in una stringa human-readable
def expr2str(expr):
    if isinstance(expr, SMExpression):
        return INV_PR[expr.member]
    elif isinstance(expr, SIExpression):
        return INV_PR[expr.principal] + "." + INV_RN[expr.roleName]
    elif isinstance(expr, LIExpression):
        return INV_PR[expr.principal] + "." + INV_RN[expr.roleNameA] + "." + INV_RN[expr.roleNameB]
    elif isinstance(expr, IIExpression):
        return INV_PR[expr.principalA] + "." + INV_RN[expr.roleNameA] + " ∩ " + INV_PR[expr.principalB] + "." + INV_RN[expr.roleNameB]


# ----------------------------------------------------- 

# Registra ruoli e credenziali per istanziare la policy di test EPapers
print("Loading policy... ", end='')

d.newRole(RN['recommendationFrom'], {'from': PR['Alice']})
d.newRole(RN['reviewer'], {'from': PR['RecSys']})
d.newRole(RN['expert'], {'from': PR['RecSys']})
d.newRole(RN['buyer'], {'from': PR['RecSys']})
d.newRole(RN['university'], {'from': PR['RecSys']})
d.newRole(RN['professor'], {'from': PR['RecSys']})
d.newRole(RN['university'], {'from': PR['StateA']})


print(addressesOfUniversities)
for uniAddr in addressesOfUniversities:
    d.newRole(RN['professor'], {'from': uniAddr})

for idx, principalAddr in enumerate(addressesOfEligiblesExpert):
    # Registra il principal come professore di una delle università
    d.addSimpleMember(RN['professor'], SMExpression(principalAddr), 100, {'from': addressesOfUniversities[idx % len(addressesOfUniversities)]})
for idx, principalAddr in enumerate(addressesOfEligiblesBuyer):
    # Registra buyer a RecSys
    d.addSimpleMember(RN['buyer'], SMExpression(principalAddr), 100, {'from': PR['RecSys']})
for uniAddr in addressesOfUniversities:
    # StateA.university ←− Uni_X
    d.addSimpleMember(RN['university'], SMExpression(uniAddr), 100, {'from': PR['StateA']})
# RecSys.university ←− StateA.university
d.addSimpleInclusion(RN['university'], SIExpression(PR['StateA'], RN['university']), 100, {'from': PR['RecSys']})
# RecSys.expert ←− RecSys.university.professor
d.addLinkedInclusion(RN['expert'], LIExpression(PR['RecSys'], RN['university'], RN['professor']), 100, {'from': PR['RecSys']})
# RecSys.reviewer ←− RecSys.expert e RecSys.buyer
d.addIntersectionInclusion(RN['reviewer'], IIExpression(PR['RecSys'], RN['expert'], PR['RecSys'], RN['buyer']), 50, {'from': PR['RecSys']})
# Alice.recommendationFrom ←− RecSys.expert
d.addSimpleInclusion(RN['recommendationFrom'], SIExpression(PR['RecSys'], RN['expert']), 100, {'from': PR['Alice']})

print("Done")

# ----------------------------------------------------- 

# Effettua una ricerca locale di tutti i membri a cui risulta assegnato il ruolo EPapers.canAccess
print("\nSearching... ", end='')
solutions = d.search(SIExpression(PR['Alice'], RN['recommendationFrom']))
print(f"Found solutions: {len(solutions)}")
filename = "testScenarioCnEligibles"+str(nEligibles)+".csv"
if os.path.exists(filename):
    append_write = 'a' # append if already exists
else:
    append_write = 'w' # make a new file if not
with open(filename,append_write) as f1:
    writer=csv.writer(f1,delimiter=' ', lineterminator='\n')
    row=[]
    # Per ciascun membro trovato, costruiscine la dimostrazione per il metodo di verifica on-chain sulla base dei paths nelle soluzioni
    for idx, currSol in enumerate(solutions.values()):
        print(f'\nSolution #{idx+1}: member={INV_PR[currSol.member]}, weight={currSol.weight}')
        proofStrs = []
        proof = []
        for currEdge in currSol.path:
            if not isinstance(currEdge.toNode.expr, LIExpression):
                proofStrs.append(expr2str(currEdge.toNode.expr) + ' ←- ' + expr2str(currEdge.fromNode.expr))
                proof.append(currEdge.toNode.expr.id)
                proof.append(currEdge.fromNode.expr.id)

        # Verifica la dimostrazione on-chain
        print('On-chain verification proof:')
        pprint(proofStrs)

        verifGas = d.contract.functions.verifyProof(proof, currSol.reqStackSize).estimateGas()
        verifRes = d.verifyProof(proof, currSol.reqStackSize)
        if verifRes['principal'] != PR['Alice'] or verifRes['rolename'] != RN['recommendationFrom'] or verifRes['member'] != currSol.member:
            print("ERROR: invalid proof for current solution!")
        else:
            verifRes['principal'] = INV_PR[verifRes['principal']]
            verifRes['rolename'] = INV_RN[verifRes['rolename']]
            verifRes['member'] = INV_PR[verifRes['member']]
        print(f'On-chain verification gas: {verifGas}')
        row.append(verifGas)
        print(f'On-chain verification result: {verifRes}')
    writer.writerow(row)